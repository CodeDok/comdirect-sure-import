@echo off
chcp 1252 >nul
echo.
echo Bitte vor der Verwendung diese Datei bearbeiten.
echo Die nachfolgenden Pfade sollten angepasst werden.
echo "doscpath" stimmt fast garantiert nicht auf diesem PC.
echo "pythonexe" und "scriptpath" sollten stimmen, wenn keine benutzerdefinierten Pfade angewendet wurden.
echo Danach diese Zeilen und die darauffolgenden "pause" / "exit" Befehle löschen.
pause
exit
SET docspath="C:%HOMEPATH%\Documents\Kontoauszuege"
SET pythonexe="C:%HOMEPATH%\.conda\envs\parse-kontoauszug\python.exe"
SET scriptpath="C:%HOMEPATH%\Downloads\parse-kontoauszug\parse-kontoauszug.py"
SET outname=girokonto.csv
echo.
echo Alle Finanzreport-pdfs im Zielordner werden gelesen.
echo Zielordner: %docspath%
echo Die Zieldatei %outname% wird im Verzeichnis dieses scripts abgespeichert.
echo Dateien jetzt lesen?
pause
%pythonexe% %scriptpath% -p %docspath% -o %outname%
echo Vorgang abgeschlossen. Beliebige Taste druecken um zu schliessen.
pause