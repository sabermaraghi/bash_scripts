Database Backup Automation Script

Overview

This Python script automates regular backups for MySQL and PostgreSQL databases. It creates backup directories, manages permissions, performs backups using mysqldump or pg_dump, compresses the output, and schedules the process using the schedule library. Old backups are automatically cleaned up based on a retention policy.

Features





Supports MySQL and PostgreSQL databases



Compresses backups using gzip



Configurable via YAML file



Automatic folder creation with secure permissions (750)



Scheduled backups with customizable intervals



Retention policy for old backups



Comprehensive logging to file and console



Error handling and retry mechanisms

Prerequisites





Python 3.8+



Required Python packages: pyyaml, schedule



For MySQL: mysqldump command-line tool



For PostgreSQL: pg_dump command-line tool



gzip for compression

Installation





Clone the repository:

git clone https://github.com/yourusername/database-backup.git
cd database-backup



Install dependencies:

pip install pyyaml schedule



Configure the backup settings in backup_config.yaml:





Set database type (mysql or postgres)



Specify database credentials and connection details



Define backup directory, retention period, and backup interval

Usage





Ensure the database tools (mysqldump or pg_dump) are installed and accessible.



Update backup_config.yaml with your settings.



Run the script:

python backup_database.py



The script will create the backup directory, set permissions, and start the backup schedule.

Configuration

Edit backup_config.yaml to customize:





database: Database type, host, port, name, user, and password



backup.directory: Path to store backups



backup.retention_days: Number of days to keep backups



backup.interval_hours: Frequency of backups in hours

Logging





Logs are written to backup.log and displayed on the console.



Includes backup success/failure, cleanup operations, and errors.

Deployment





Run as a background process using nohup or a process manager like systemd.



Example with nohup:

nohup python backup_database.py &



For production, consider using a systemd service for better process management.

Contributing





Fork the repository.



Create a feature branch (git checkout -b feature/YourFeature).



Commit changes (git commit -m 'Add YourFeature').



Push to the branch (git push origin feature/YourFeature).



Open a Pull Request.

License

MIT License - see LICENSE for details.
