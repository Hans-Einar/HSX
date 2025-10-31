"""Unit tests for hsx-cc-build.py (HSXBuilder class)"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import importlib.util
spec = importlib.util.spec_from_file_location("hsx_cc_build", Path(__file__).resolve().parents[1] / "hsx-cc-build.py")
hsx_cc_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hsx_cc_build)

HSXBuilder = hsx_cc_build.HSXBuilder
HSXBuildError = hsx_cc_build.HSXBuildError


def make_args(**kwargs):
    """Create a mock args object with default values"""
    defaults = {
        'sources': [],
        'directory': None,
        'build_dir': None,
        'debug': False,
        'output': None,
        'app_name': None,
        'no_make': False,
        'jobs': None,
        'verbose': False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestHSXBuilderInit:
    """Test HSXBuilder initialization"""
    
    def test_init_default_build_dir(self, tmp_path):
        """Test default build directory is 'build'"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            assert builder.build_dir == Path('build')
            assert builder.project_root == tmp_path
    
    def test_init_debug_build_dir(self, tmp_path):
        """Test debug flag sets build/debug directory"""
        args = make_args(debug=True)
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            assert builder.build_dir == Path('build/debug')
    
    def test_init_custom_build_dir(self, tmp_path):
        """Test custom build directory override"""
        args = make_args(build_dir='custom/output')
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            assert builder.build_dir == Path('custom/output')
    
    def test_init_creates_build_dir(self, tmp_path):
        """Test build directory is created if it doesn't exist"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            assert builder.build_dir.exists()
    
    def test_init_with_directory_change(self, tmp_path):
        """Test -C flag changes to directory"""
        target_dir = tmp_path / "subdir"
        target_dir.mkdir()
        args = make_args(directory=str(target_dir))
        builder = HSXBuilder(args)
        assert Path.cwd() == target_dir


class TestHSXBuilderFindTool:
    """Test tool discovery logic"""
    
    def test_find_tool_in_python_dir(self, tmp_path):
        """Test finding tool in python/ directory"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            # Create python/hsx-llc.py
            python_dir = tmp_path / 'python'
            python_dir.mkdir()
            tool_path = python_dir / 'hsx-llc.py'
            tool_path.touch()
            
            builder = HSXBuilder(args)
            found_tool = builder.find_tool('hsx-llc.py')
            assert found_tool == tool_path
    
    def test_find_tool_in_path(self, tmp_path):
        """Test finding tool in system PATH"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            
            # Mock shutil.which to return a path
            with patch('shutil.which', return_value='/usr/bin/clang'):
                found_tool = builder.find_tool('clang')
                assert found_tool == Path('/usr/bin/clang')
    
    def test_find_tool_not_found(self, tmp_path):
        """Test error when tool not found"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            
            with patch('shutil.which', return_value=None):
                try:
                    builder.find_tool('nonexistent-tool')
                    assert False, "Should have raised HSXBuildError"
                except HSXBuildError as e:
                    assert 'not found' in str(e)


class TestHSXBuilderCompile:
    """Test compilation stages"""
    
    def test_compile_c_to_ll_basic(self, tmp_path):
        """Test C to LLVM IR compilation"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            c_file = tmp_path / "test.c"
            c_file.write_text("int main() { return 0; }")
            
            # Mock subprocess.run
            with patch.object(builder, 'run_command') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                ll_file = builder.compile_c_to_ll(c_file)
                
                # Check that clang was called
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                assert 'clang' in cmd
                assert '-S' in cmd
                assert '-emit-llvm' in cmd
                assert ll_file.name == 'test.ll'
    
    def test_compile_c_to_ll_debug_flags(self, tmp_path):
        """Test debug flags are passed to clang"""
        args = make_args(debug=True)
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            c_file = tmp_path / "test.c"
            c_file.write_text("int main() { return 0; }")
            
            with patch.object(builder, 'run_command') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                builder.compile_c_to_ll(c_file)
                
                cmd = mock_run.call_args[0][0]
                assert '-g' in cmd
                assert '-O0' in cmd
                # Check for -fdebug-prefix-map
                assert any('-fdebug-prefix-map' in str(arg) for arg in cmd)


class TestHSXBuilderLower:
    """Test LLVM IR lowering"""
    
    def test_lower_ll_to_asm_basic(self, tmp_path):
        """Test lowering LLVM IR to MVASM"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            ll_file = builder.build_dir / "test.ll"
            ll_file.write_text("; dummy IR")
            
            # Mock find_tool and run_command
            with patch.object(builder, 'find_tool') as mock_find:
                mock_find.return_value = Path('/fake/hsx-llc.py')
                with patch.object(builder, 'run_command') as mock_run:
                    mock_run.return_value = Mock(returncode=0)
                    
                    asm_file, dbg_file = builder.lower_ll_to_asm(ll_file)
                    
                    assert asm_file.name == 'test.asm'
                    assert dbg_file is None  # No debug in non-debug build
    
    def test_lower_ll_to_asm_with_debug(self, tmp_path):
        """Test debug info generation during lowering"""
        args = make_args(debug=True)
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            ll_file = builder.build_dir / "test.ll"
            ll_file.write_text("; dummy IR")
            
            with patch.object(builder, 'find_tool') as mock_find:
                mock_find.return_value = Path('/fake/hsx-llc.py')
                with patch.object(builder, 'run_command') as mock_run:
                    mock_run.return_value = Mock(returncode=0)
                    
                    asm_file, dbg_file = builder.lower_ll_to_asm(ll_file)
                    
                    assert dbg_file is not None
                    assert dbg_file.name == 'test.dbg'
                    
                    # Check --emit-debug flag was passed
                    cmd = mock_run.call_args[0][0]
                    assert '--emit-debug' in cmd


class TestHSXBuilderAssemble:
    """Test assembly stage"""
    
    def test_assemble_to_hxo(self, tmp_path):
        """Test assembling MVASM to HXO"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            asm_file = builder.build_dir / "test.asm"
            asm_file.write_text(".text\nLDI R0, 42\nRET")
            
            with patch.object(builder, 'find_tool') as mock_find:
                mock_find.return_value = Path('/fake/asm.py')
                with patch.object(builder, 'run_command') as mock_run:
                    mock_run.return_value = Mock(returncode=0)
                    
                    hxo_file = builder.assemble_to_hxo(asm_file)
                    
                    assert hxo_file.name == 'test.hxo'
                    assert 'asm.py' in str(mock_run.call_args[0][0])


class TestHSXBuilderLink:
    """Test linking stage"""
    
    def test_link_to_hxe_basic(self, tmp_path):
        """Test linking HXO files to HXE"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            hxo_files = [builder.build_dir / "test.hxo"]
            
            with patch.object(builder, 'find_tool') as mock_find:
                mock_find.return_value = Path('/fake/hld.py')
                with patch.object(builder, 'run_command') as mock_run:
                    mock_run.return_value = Mock(returncode=0)
                    
                    hxe_file = builder.link_to_hxe(hxo_files, [])
                    
                    assert hxe_file.name == 'app.hxe'
                    cmd = mock_run.call_args[0][0]
                    assert 'hld.py' in str(cmd)
                    assert '--app-name' in cmd
    
    def test_link_to_hxe_with_debug(self, tmp_path):
        """Test linking with debug info"""
        args = make_args(debug=True, output='test.hxe')
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            hxo_files = [builder.build_dir / "test.hxo"]
            dbg_files = [builder.build_dir / "test.dbg"]
            
            with patch.object(builder, 'find_tool') as mock_find:
                mock_find.return_value = Path('/fake/hld.py')
                with patch.object(builder, 'run_command') as mock_run:
                    mock_run.return_value = Mock(returncode=0)
                    
                    hxe_file = builder.link_to_hxe(hxo_files, dbg_files)
                    
                    cmd = mock_run.call_args[0][0]
                    assert '--debug-info' in cmd
                    assert '--emit-sym' in cmd


class TestHSXBuilderSourcesJson:
    """Test sources.json generation"""
    
    def test_generate_sources_json(self, tmp_path):
        """Test sources.json file generation"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            
            # Create source files
            src_file = tmp_path / "test.c"
            src_file.write_text("int main() {}")
            
            builder.generate_sources_json([src_file])
            
            sources_json = builder.build_dir / 'sources.json'
            assert sources_json.exists()
            
            data = json.loads(sources_json.read_text())
            assert data['version'] == 1
            assert 'project_root' in data
            assert 'sources' in data
            assert len(data['sources']) == 1
            assert data['sources'][0]['file'] == 'test.c'


class TestHSXBuilderBuildModes:
    """Test different build modes"""
    
    def test_build_with_make(self, tmp_path):
        """Test Makefile-based build"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            # Create Makefile
            makefile = tmp_path / "Makefile"
            makefile.write_text("all:\n\t@echo Building")
            
            builder = HSXBuilder(args)
            
            with patch.object(builder, 'run_command') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                builder.build_with_make()
                
                # Check make was called
                cmd = mock_run.call_args[0][0]
                assert 'make' in cmd
                assert 'all' in cmd
    
    def test_build_with_make_debug_target(self, tmp_path):
        """Test Makefile build with debug target"""
        args = make_args(debug=True)
        with patch('os.getcwd', return_value=str(tmp_path)):
            makefile = tmp_path / "Makefile"
            makefile.write_text("debug:\n\t@echo Debug build")
            
            builder = HSXBuilder(args)
            
            with patch.object(builder, 'run_command') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                builder.build_with_make()
                
                cmd = mock_run.call_args[0][0]
                assert 'debug' in cmd
    
    def test_build_with_make_parallel_jobs(self, tmp_path):
        """Test parallel make with -j flag"""
        args = make_args(jobs=4)
        with patch('os.getcwd', return_value=str(tmp_path)):
            makefile = tmp_path / "Makefile"
            makefile.write_text("all:\n\t@echo Building")
            
            builder = HSXBuilder(args)
            
            with patch.object(builder, 'run_command') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                builder.build_with_make()
                
                cmd = mock_run.call_args[0][0]
                assert '-j' in cmd
                assert '4' in cmd


class TestHSXBuilderErrorHandling:
    """Test error handling"""
    
    def test_run_command_failure(self, tmp_path):
        """Test command failure raises HSXBuildError"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            
            # Mock subprocess.run to raise CalledProcessError
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(
                    1, ['fake', 'command'], stderr="Error message"
                )
                
                try:
                    builder.run_command(['fake', 'command'])
                    assert False, "Should have raised HSXBuildError"
                except HSXBuildError as e:
                    assert 'failed' in str(e).lower()
    
    def test_build_with_make_no_makefile(self, tmp_path):
        """Test error when Makefile doesn't exist"""
        args = make_args()
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            
            try:
                builder.build_with_make()
                assert False, "Should have raised HSXBuildError"
            except HSXBuildError as e:
                assert 'makefile' in str(e).lower()


class TestHSXBuilderVerboseMode:
    """Test verbose output"""
    
    def test_log_when_verbose(self, tmp_path, capsys):
        """Test log messages when verbose is enabled"""
        args = make_args(verbose=True)
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            builder.log("Test message")
            
            captured = capsys.readouterr()
            assert "Test message" in captured.out
    
    def test_no_log_when_not_verbose(self, tmp_path, capsys):
        """Test no log messages when verbose is disabled"""
        args = make_args(verbose=False)
        with patch('os.getcwd', return_value=str(tmp_path)):
            builder = HSXBuilder(args)
            builder.log("Test message")
            
            captured = capsys.readouterr()
            assert "Test message" not in captured.out
