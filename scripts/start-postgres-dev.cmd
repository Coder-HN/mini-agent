@echo off
set PG=E:\CodeSupport\postgresql\bin
set DATA=E:\CodeSupport\postgresql\data_dev
"%PG%\pg_ctl.exe" status -D "%DATA%"
if errorlevel 1 (
  echo starting...
  "%PG%\pg_ctl.exe" start -D "%DATA%" -l "%DATA%\log.txt"
)
"%PG%\pg_isready.exe" -h 127.0.0.1 -p 5432
"%PG%\psql.exe" -h 127.0.0.1 -U postgres -d postgres -c "SELECT version();"
"%PG%\psql.exe" -h 127.0.0.1 -U postgres -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='min_agent'" | findstr 1 >nul
if errorlevel 1 (
  echo creating database min_agent...
  "%PG%\createdb.exe" -h 127.0.0.1 -U postgres min_agent
) else (
  echo database min_agent exists
)
"%PG%\psql.exe" -h 127.0.0.1 -U postgres -d min_agent -c "SELECT current_database();"
