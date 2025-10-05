@echo off
setlocal
call "%~dp0hsx-env.bat"
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set OUTDIR=%ROOT%\examples\tests
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

set LLTMP=%OUTDIR%\half_main.bc
set LLTMP2=%OUTDIR%\half_ops.bc
set LLALL=%OUTDIR%\half_main_link.bc
set LLOPT=%OUTDIR%\half_main_opt.bc
set LLTXT=%ROOT%\examples\c\half_main.ll

if exist "%LLTMP%" del "%LLTMP%"
if exist "%LLTMP2%" del "%LLTMP2%"
if exist "%LLALL%" del "%LLALL%"
if exist "%LLOPT%" del "%LLOPT%"

"%HSX_CLANG%" -c -emit-llvm -O0 -fno-builtin -fno-inline -Xclang -disable-O0-optnone "%ROOT%\examples\c\half_main.c" -o "%LLTMP%"
if errorlevel 1 goto :error
"%HSX_CLANG%" -c -emit-llvm -O0 -fno-builtin -fno-inline -Xclang -disable-O0-optnone "%ROOT%\examples\c\half.c" -o "%LLTMP2%"
if errorlevel 1 goto :error
llvm-link "%LLTMP%" "%LLTMP2%" -o "%LLALL%"
if errorlevel 1 goto :error
opt -passes=mem2reg,instcombine "%LLALL%" -o "%LLOPT%"
if errorlevel 1 goto :error
llvm-dis "%LLOPT%" -o "%LLTXT%"
if errorlevel 1 goto :error

echo [half_main.bat] Lowering LLVM -^> HSX assembly...
call %HSX_PY% "%ROOT%\python\hsx-llc.py" "%LLTXT%" -o "%OUTDIR%\half_main.mvasm"
if errorlevel 1 goto :error

echo [half_main.bat] Assembling -^> .hxe image...
call %HSX_PY% "%ROOT%\python\asm.py" "%OUTDIR%\half_main.mvasm" -o "%OUTDIR%\half_main.hxe" -v
if errorlevel 1 goto :error

echo [half_main.bat] Running in HSX VM...
call %HSX_PY% "%ROOT%\python\host_vm.py" "%OUTDIR%\half_main.hxe" --trace --max-steps 1000
if errorlevel 1 goto :error

echo Done.
goto :EOF

:error
echo Toolchain failed with exit code %errorlevel%.
exit /b %errorlevel%
