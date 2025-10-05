@echo off
setlocal
call "%~dp0hsx-env.bat"
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set OUTDIR=%ROOT%\examples\tests
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

set SRC_LIB=%ROOT%\examples\c\link_lib.c
set SRC_MAIN=%ROOT%\examples\c\link_main.c
set LL_LIB=%ROOT%\examples\c\link_lib.ll
set LL_MAIN=%ROOT%\examples\c\link_main.ll
set ASM_LIB=%OUTDIR%\link_lib.mvasm
set ASM_MAIN=%OUTDIR%\link_main.mvasm
set HXO_LIB=%OUTDIR%\link_lib.hxo
set HXO_MAIN=%OUTDIR%\link_main.hxo
set HXE_OUT=%OUTDIR%\link_demo.hxe

set CLANG_LOG=%OUTDIR%\clang_link.log

"%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-inline "%SRC_LIB%" -o "%LL_LIB%" 1>nul 2>"%CLANG_LOG%"
if errorlevel 1 (
    findstr /C:"unknown argument" "%CLANG_LOG%" >nul 2>&1
    if not errorlevel 1 (
        echo [link_test.bat] Retrying clang on link_lib.c without unsupported flags...
        "%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin "%SRC_LIB%" -o "%LL_LIB%"
        if errorlevel 1 goto :error
    ) else (
        type "%CLANG_LOG%"
        goto :error
    )
)

"%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin -fno-inline "%SRC_MAIN%" -o "%LL_MAIN%" 1>nul 2>>"%CLANG_LOG%"
if errorlevel 1 (
    findstr /C:"unknown argument" "%CLANG_LOG%" >nul 2>&1
    if not errorlevel 1 (
        echo [link_test.bat] Retrying clang on link_main.c without unsupported flags...
        "%HSX_CLANG%" -S -emit-llvm -O0 -fno-builtin "%SRC_MAIN%" -o "%LL_MAIN%"
        if errorlevel 1 goto :error
    ) else (
        type "%CLANG_LOG%"
        goto :error
    )
)
del "%CLANG_LOG%" >nul 2>&1

call %HSX_PY% "%ROOT%\python\hsx-llc.py" "%LL_LIB%" -o "%ASM_LIB%"
if errorlevel 1 goto :error
call %HSX_PY% "%ROOT%\python\hsx-llc.py" "%LL_MAIN%" -o "%ASM_MAIN%"
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\asm.py" "%ASM_LIB%" --emit-hxo -o "%HXO_LIB%"
if errorlevel 1 goto :error
call %HSX_PY% "%ROOT%\python\asm.py" "%ASM_MAIN%" --emit-hxo -o "%HXO_MAIN%"
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\hld.py" "%HXO_LIB%" "%HXO_MAIN%" -o "%HXE_OUT%"
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\host_vm.py" "%HXE_OUT%"
if errorlevel 1 goto :error

echo Done.
goto :EOF

:error
echo link_test pipeline failed with exit code %errorlevel%.
exit /b %errorlevel%
