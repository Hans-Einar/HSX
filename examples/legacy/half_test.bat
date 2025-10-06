@echo off
setlocal
call "%~dp0hsx-env.bat"
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set OUTDIR=%ROOT%\examples\tests
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

"%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-tree-sra -fno-inline -fno-simplifycfg "%ROOT%\examples\c\half.c" -o "%ROOT%\examples\c\half.ll" 1>nul 2>"%OUTDIR%\clang_half.log"
if errorlevel 1 (
    findstr /C:"unknown argument" "%OUTDIR%\clang_half.log" >nul 2>&1
    if not errorlevel 1 (
        echo [half_test.bat] Retrying clang without unsupported flags...
        "%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-inline "%ROOT%\examples\c\half.c" -o "%ROOT%\examples\c\half.ll"
        if errorlevel 1 goto :error
    ) else (
        type "%OUTDIR%\clang_half.log"
        goto :error
    )
)
del "%OUTDIR%\clang_half.log" >nul 2>&1

call %HSX_PY% "%ROOT%\python\hsx-llc.py" "%ROOT%\examples\c\half.ll" -o "%OUTDIR%\half_from_c.mvasm"
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\asm.py" "%OUTDIR%\half_from_c.mvasm" -o "%OUTDIR%\half_from_c.hxe" -v
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\platforms\\python\\host_vm.py" "%OUTDIR%\half_from_c.hxe" --trace
if errorlevel 1 goto :error

echo Done.
goto :EOF

:error
echo Toolchain failed with exit code %errorlevel%.
exit /b %errorlevel%
