@echo off
setlocal
call "%~dp0hsx-env.bat"
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set OUTDIR=%ROOT%\examples\tests
set SRC=%OUTDIR%\data_section.mvasm
set HXE=%OUTDIR%\data_section.hxe

if not exist "%OUTDIR%" mkdir "%OUTDIR%"

call %HSX_PY% "%ROOT%\python\asm.py" "%SRC%" -o "%HXE%" -v
if errorlevel 1 goto :error

call %HSX_PY% "%ROOT%\python\host_vm.py" "%HXE%" --trace
if errorlevel 1 goto :error

echo Done.
goto :EOF

:error
echo data_section_test failed with exit code %errorlevel%.
exit /b %errorlevel%
