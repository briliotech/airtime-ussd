@echo off
set /p msg="Enter commit message: "

echo Adding all changes...
git add .

echo Committing with message: %msg%
git commit -m "%msg%"

echo Pushing to origin...
git push origin

echo Done!
pause
