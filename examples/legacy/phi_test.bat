@echo off
setlocal
call "%~dp0hsx-env.bat"
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set OUTDIR=%ROOT%\examples\tests
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
set TMP_LL=%OUTDIR%\phi_tmp.ll
set TMP_MEM2REG=%OUTDIR%\phi_mem2reg.ll

"%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-tree-sra -fno-inline -fno-simplifycfg "%ROOT%\examples\c\phi.c" -o "%TMP_LL%" 1>nul 2>"%OUTDIR%\clang_phi.log"
if errorlevel 1 (
    findstr /C:"unknown argument" "%OUTDIR%\clang_phi.log" >nul 2>&1
    if not errorlevel 1 (
        echo [phi_test.bat] Retrying clang without unsupported flags...
        "%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-inline "%ROOT%\examples\c\phi.c" -o "%TMP_LL%"
        if errorlevel 1 goto :error
    ) else (
        type "%OUTDIR%\clang_phi.log"
        goto :error
    )
)
del "%OUTDIR%\clang_phi.log" >nul 2>&1

opt -S -passes=mem2reg "%TMP_LL%" -o "%TMP_MEM2REG%"
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\hsx-llc.py" "%TMP_MEM2REG%" -o "%OUTDIR%\phi_from_c.mvasm"
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\asm.py" "%OUTDIR%\phi_from_c.mvasm" -o "%OUTDIR%\phi_from_c.hxe" -v
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\platforms\\python\\host_vm.py" "%OUTDIR%\phi_from_c.hxe" --trace
if errorlevel 1 goto :error

echo Done.
goto :EOF

:error
echo Toolchain failed with exit code %errorlevel%.
exit /b %errorlevel%
