#!/usr/bin/env python3
"""
HSX Unified Build Script
Orchestrates the complete build pipeline from C source to debuggable HXE executable.

Usage:
    hsx-cc-build.py [options] <source_files...>
    hsx-cc-build.py --debug -C /path/to/project
    hsx-cc-build.py --debug -b build/debug main.c src/utils.c

Options:
    -C DIR              Change to directory before building
    -b, --build-dir DIR Specify build directory (default: ./build or ./build/debug)
    --debug             Enable debug build with symbols and debug metadata
    -o, --output NAME   Output executable name (default: app.hxe)
    --app-name NAME     Application name for HXE header
    --no-make           Skip make invocation, build files directly
    -j JOBS             Parallel jobs for make (default: auto)
    --clean             Remove build directory before building
    -v, --verbose       Verbose output
    -h, --help          Show this help message
    
Debug Build Output:
    build/debug/app.hxe     - Executable
    build/debug/app.sym     - Symbol file with line numbers
    build/debug/sources.json - Source file path mappings
    build/debug/*.dbg       - Intermediate debug info files
    build/debug/*.hxo       - Object files

Examples:
    # Debug build using Makefile
    hsx-cc-build.py --debug -C /path/to/project
    
    # Debug build direct files
    hsx-cc-build.py --debug main.c utils.c -o myapp.hxe
    
    # Release build
    hsx-cc-build.py -C /path/to/project -b build/release
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timezone


def _select_symbol(preferred: str, fallback: str) -> str:
    """Return preferred symbol when it can be encoded, otherwise fallback."""
    streams = (sys.stdout, sys.stderr)
    for stream in streams:
        encoding = getattr(stream, "encoding", None)
        if not encoding:
            continue
        try:
            preferred.encode(encoding)
        except UnicodeEncodeError:
            return fallback
    return preferred


SUCCESS_MARK = _select_symbol("✓", "[OK]")
FAIL_MARK = _select_symbol("✗", "[ERROR]")

class HSXBuildError(Exception):
    """Build error exception"""
    pass


class HSXBuilder:
    """Main build orchestrator"""
    
    def __init__(self, args):
        self.args = args
        self.verbose = args.verbose
        self.debug_prefix_map: Optional[str] = None
        self.debug_prefix_map_flag: Optional[str] = None
        self.debug_env: Dict[str, str] = {}

        # Determine working directory
        if args.directory:
            os.chdir(args.directory)
            if self.verbose:
                print(f"Changed directory to: {os.getcwd()}")
        
        self.project_root = Path.cwd()
        
        # Determine build directory
        if args.build_dir:
            self.build_dir = Path(args.build_dir)
        elif args.debug:
            self.build_dir = Path('build/debug')
        else:
            self.build_dir = Path('build')

        if args.clean and self.build_dir.exists():
            if self.verbose:
                print(f"[hsx-cc-build] Cleaning build directory: {self.build_dir}")
            shutil.rmtree(self.build_dir)

        self.build_dir.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            print(f"Project root: {self.project_root}")
            print(f"Build directory: {self.build_dir}")

        if args.debug:
            resolved_root = str(self.project_root.resolve())
            self.debug_prefix_map = f"{resolved_root}=."
            self.debug_prefix_map_flag = f"-fdebug-prefix-map={self.debug_prefix_map}"
            self.debug_env = {
                "HSX_DEBUG_PREFIX_MAP": self.debug_prefix_map,
                "DEBUG_PREFIX_MAP": self.debug_prefix_map,
            }

    def log(self, msg: str):
        """Log message if verbose"""
        if self.verbose:
            print(f"[hsx-cc-build] {msg}")
    
    def run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Run command and check result"""
        cmd_str = ' '.join(str(c) for c in cmd)
        self.log(f"Running: {cmd_str}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                env=self._command_env(),
            )
            if result.stdout and self.verbose:
                print(result.stdout)
            return result
        except subprocess.CalledProcessError as e:
            print(f"Error running command: {cmd_str}", file=sys.stderr)
            if e.stdout:
                print("STDOUT:", e.stdout, file=sys.stderr)
            if e.stderr:
                print("STDERR:", e.stderr, file=sys.stderr)
            raise HSXBuildError(f"Command failed: {cmd_str}")

    def _command_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        if self.debug_env:
            for key, value in self.debug_env.items():
                env.setdefault(key, value)
        return env
    
    def find_tool(self, tool: str) -> Path:
        """Find tool in python/ directory or PATH"""
        # Try python/ directory first
        python_dir = self.project_root / 'python'
        tool_path = python_dir / tool
        if tool_path.exists():
            return tool_path
        
        # Try PATH
        which_result = shutil.which(tool)
        if which_result:
            return Path(which_result)
        
        raise HSXBuildError(f"Tool not found: {tool}")
    
    def build_with_make(self):
        """Build using Makefile"""
        self.log("Building with make...")
        
        # Determine make target
        if self.args.debug:
            target = 'debug'
        else:
            target = 'all'
        
        # Build make command
        make_cmd = ['make', target]
        
        if self.args.jobs:
            make_cmd.extend(['-j', str(self.args.jobs)])
        
        # Check if Makefile exists
        if not (self.project_root / 'Makefile').exists():
            raise HSXBuildError("No Makefile found in project root")
        
        # Run make
        self.run_command(make_cmd)
        
        self.log("Make completed successfully")
    
    def compile_c_to_ll(self, c_file: Path) -> Path:
        """Compile C to LLVM IR"""
        ll_file = self.build_dir / c_file.with_suffix('.ll').name
        
        self.log(f"Compiling {c_file} to LLVM IR...")
        
        clang_cmd = ['clang', '-S', '-emit-llvm']
        
        if self.args.debug:
            # Debug flags with relative paths
            clang_cmd.extend([
                '-g',
                '-O0',
                self.debug_prefix_map_flag or f'-fdebug-prefix-map={self.project_root.resolve()}=.'
            ])
        else:
            clang_cmd.extend(['-O2'])
        
        clang_cmd.extend([
            str(c_file),
            '-o', str(ll_file)
        ])
        
        self.run_command(clang_cmd)
        return ll_file
    
    def lower_ll_to_asm(self, ll_file: Path) -> tuple[Path, Optional[Path]]:
        """Lower LLVM IR to MVASM"""
        asm_file = self.build_dir / ll_file.with_suffix('.asm').name
        dbg_file = None
        
        self.log(f"Lowering {ll_file} to MVASM...")
        
        hsx_llc = self.find_tool('hsx-llc.py')
        
        llc_cmd = [sys.executable, str(hsx_llc)]
        llc_cmd.extend([str(ll_file), '-o', str(asm_file)])
        
        if self.args.debug:
            dbg_file = self.build_dir / ll_file.with_suffix('.dbg').name
            llc_cmd.extend(['--emit-debug', str(dbg_file)])
        
        self.run_command(llc_cmd)
        return asm_file, dbg_file
    
    def assemble_to_hxo(self, asm_file: Path) -> Path:
        """Assemble MVASM to HXO"""
        hxo_file = self.build_dir / asm_file.with_suffix('.hxo').name
        
        self.log(f"Assembling {asm_file} to HXO...")
        
        asm_tool = self.find_tool('asm.py')
        
        asm_cmd = [
            sys.executable, str(asm_tool),
            str(asm_file),
            '-o', str(hxo_file)
        ]
        
        self.run_command(asm_cmd)
        return hxo_file
    
    def link_to_hxe(self, hxo_files: List[Path], dbg_files: List[Path]) -> Path:
        """Link HXO files to HXE"""
        output_name = self.args.output or 'app.hxe'
        hxe_file = self.build_dir / output_name
        
        self.log(f"Linking {len(hxo_files)} object files to HXE...")
        
        linker = self.find_tool('hld.py')
        
        link_cmd = [sys.executable, str(linker)]
        link_cmd.extend(str(f) for f in hxo_files)
        link_cmd.extend(['-o', str(hxe_file)])
        
        # Add app name
        app_name = self.args.app_name or output_name.replace('.hxe', '')
        link_cmd.extend(['--app-name', app_name])
        
        # Add debug info if available
        if self.args.debug and dbg_files:
            link_cmd.append('--debug-info')
            link_cmd.extend(str(f) for f in dbg_files)
            
            sym_file = hxe_file.with_suffix('.sym')
            link_cmd.extend(['--emit-sym', str(sym_file)])
        
        self.run_command(link_cmd)
        return hxe_file
    
    def generate_sources_json(self, source_files: List[Path]):
        """Generate sources.json for debugger path resolution"""
        self.log("Generating sources.json...")
        
        sources_data = {
            'version': 1,
            'project_root': str(self.project_root.resolve()),
            'build_time': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'sources': [],
            'include_paths': []
        }
        
        for src in source_files:
            src_path = Path(src)
            try:
                # Try to make relative to project root
                rel_path = src_path.resolve().relative_to(self.project_root)
            except ValueError:
                # Outside project root, use as-is
                rel_path = src_path
            
            sources_data['sources'].append({
                'file': str(rel_path),
                'path': str(src_path.resolve()),
                'relative': f"./{rel_path}"
            })
        
        # Add common include paths
        common_includes = [
            self.project_root / 'include',
            self.project_root / 'src',
            Path('/usr/local/include/hsx')
        ]
        
        for inc_path in common_includes:
            if inc_path.exists():
                sources_data['include_paths'].append(str(inc_path))
        
        sources_json = self.build_dir / 'sources.json'
        with open(sources_json, 'w') as f:
            json.dump(sources_data, f, indent=2)
        
        self.log(f"Created {sources_json}")
    
    def discover_source_files(self) -> List[Path]:
        """Discover C source files in project"""
        self.log("Discovering source files...")
        
        source_files = []
        
        # Look for common source directories
        search_dirs = [self.project_root, self.project_root / 'src']
        
        for search_dir in search_dirs:
            if search_dir.exists():
                for ext in ['*.c', '*.cpp']:
                    source_files.extend(search_dir.glob(ext))
        
        if not source_files:
            raise HSXBuildError("No source files found")
        
        self.log(f"Found {len(source_files)} source files")
        return source_files
    
    def build_direct(self, source_files: List[Path]):
        """Build source files directly without make"""
        self.log(f"Building {len(source_files)} source files...")
        
        hxo_files = []
        dbg_files = []
        
        for c_file in source_files:
            # C -> LLVM IR
            ll_file = self.compile_c_to_ll(c_file)
            
            # LLVM IR -> MVASM
            asm_file, dbg_file = self.lower_ll_to_asm(ll_file)
            if dbg_file:
                dbg_files.append(dbg_file)
            
            # MVASM -> HXO
            hxo_file = self.assemble_to_hxo(asm_file)
            hxo_files.append(hxo_file)
        
        # Link all HXO files
        hxe_file = self.link_to_hxe(hxo_files, dbg_files)
        
        # Generate sources.json for debug builds
        if self.args.debug:
            self.generate_sources_json(source_files)
        
        self.log(f"Build complete: {hxe_file}")
        return hxe_file
    
    def build(self):
        """Main build entry point"""
        try:
            if self.args.no_make or self.args.sources:
                # Direct build
                if self.args.sources:
                    source_files = [Path(s) for s in self.args.sources]
                else:
                    source_files = self.discover_source_files()
                
                self.build_direct(source_files)
            else:
                # Build with make
                self.build_with_make()
                
                # Post-process for debug builds
                if self.args.debug:
                    # Try to find source files for sources.json
                    try:
                        source_files = self.discover_source_files()
                        self.generate_sources_json(source_files)
                    except HSXBuildError:
                        self.log("Warning: Could not generate sources.json")
            
            print(f"\n{SUCCESS_MARK} Build successful!")
            print(f"  Output: {self.build_dir}")
            
            if self.args.debug:
                print(f"  Debug files:")
                print(f"    - {self.build_dir}/*.hxe (executable)")
                print(f"    - {self.build_dir}/*.sym (symbols)")
                print(f"    - {self.build_dir}/sources.json (path map)")
        
        except HSXBuildError as e:
            print(f"\n{FAIL_MARK} Build failed: {e}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print(f"\n{FAIL_MARK} Build interrupted", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"\n{FAIL_MARK} Unexpected error: {e}", file=sys.stderr)
            if self.verbose:
                import traceback
                traceback.print_exc()
            return 1
        
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='HSX Unified Build Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'sources',
        nargs='*',
        help='Source files to build (if not using make)'
    )
    
    parser.add_argument(
        '-C', '--directory',
        metavar='DIR',
        help='Change to directory before building'
    )
    
    parser.add_argument(
        '-b', '--build-dir',
        metavar='DIR',
        help='Build directory (default: ./build or ./build/debug for --debug)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug build with symbols'
    )
    
    parser.add_argument(
        '-o', '--output',
        metavar='NAME',
        help='Output executable name (default: app.hxe)'
    )
    
    parser.add_argument(
        '--app-name',
        metavar='NAME',
        help='Application name for HXE header'
    )
    
    parser.add_argument(
        '--no-make',
        action='store_true',
        help='Skip make, build files directly'
    )
    
    parser.add_argument(
        '-j', '--jobs',
        type=int,
        metavar='N',
        help='Parallel jobs for make'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Remove build directory before building'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    builder = HSXBuilder(args)
    return builder.build()


if __name__ == '__main__':
    sys.exit(main())
