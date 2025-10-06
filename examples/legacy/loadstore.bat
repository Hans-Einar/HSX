@echo off
setlocal
call "%~dp0hsx-env.bat"
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set OUTDIR=%ROOT%\examples\tests
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

"%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-tree-sra -fno-inline -fno-simplifycfg "%ROOT%\examples\c\loadstore.c" -o "%ROOT%\examples\c\loadstore.ll" 1>nul 2>"%OUTDIR%\clang.log"
if errorlevel 1 (
    findstr /C:"unknown argument" "%OUTDIR%\clang.log" >nul 2>&1
    if not errorlevel 1 (
        echo [loadstore.bat] Retrying clang without unsupported flags...
        "%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-inline "%ROOT%\examples\c\loadstore.c" -o "%ROOT%\examples\c\loadstore.ll"
        if errorlevel 1 goto :error
    ) else (
        type "%OUTDIR%\clang.log"
        goto :error
    )
)
del "%OUTDIR%\clang.log" >nul 2>&1

call %HSX_PY% "%ROOT%\python\hsx-llc.py" "%ROOT%\examples\c\loadstore.ll" -o "%OUTDIR%\loadstore_from_c.mvasm"
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\asm.py" "%OUTDIR%\loadstore_from_c.mvasm" -o "%OUTDIR%\loadstore_from_c.hxe" -v
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\platforms\\python\\host_vm.py" "%OUTDIR%\loadstore_from_c.hxe" --trace
if errorlevel 1 goto :error

echo Done.
goto :EOF

:error
echo Toolchain failed with exit code %errorlevel%.
exit /b %errorlevel%
