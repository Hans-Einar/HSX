@echo off
setlocal
call "%~dp0hsx-env.bat"
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set OUTDIR=%ROOT%\examples\tests
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

set SRC=%ROOT%\examples\c\extern_pair.c
set LL=%ROOT%\examples\c\extern_pair.ll
set ASM_OUT=%OUTDIR%\extern_pair_from_c.mvasm
set HXE_OUT=%OUTDIR%\extern_pair_from_c.hxe
set CLANG_LOG=%OUTDIR%\clang_extern_pair.log

"%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-tree-sra -fno-inline -fno-simplifycfg "%SRC%" -o "%LL%" 1>nul 2>"%CLANG_LOG%"
if errorlevel 1 (
    findstr /C:"unknown argument" "%CLANG_LOG%" >nul 2>&1
    if not errorlevel 1 (
        echo [extern_pair_test.bat] Retrying clang without unsupported flags...
        "%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-inline "%SRC%" -o "%LL%"
        if errorlevel 1 goto :error
    ) else (
        type "%CLANG_LOG%"
        goto :error
    )
)
del "%CLANG_LOG%" >nul 2>&1

call %HSX_PY% "%ROOT%\python\hsx-llc.py" "%LL%" -o "%ASM_OUT%"
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\asm.py" "%ASM_OUT%" -o "%HXE_OUT%" -v
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\host_vm.py" "%HXE_OUT%" --trace
if errorlevel 1 goto :error

echo Done.
goto :EOF

:error
echo Toolchain failed with exit code %errorlevel%.
exit /b %errorlevel%
