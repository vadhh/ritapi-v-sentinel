# 🚀 RitAPI V-Sentinel

RitAPI V-Sentinel is a Django project designed to provide an advanced API solution. This repository includes an automated setup script (based on the provided Bash file) to simplify the installation and running of the project in a local development environment.

## ⚠️ Prerequisites

Before running the setup script, ensure your system meets the following requirements:

| Requirement | Details |
| :--- | :--- |
| **Python** | Version 3.8 or higher. |
| **PostgreSQL Client** | The `psql` and `createdb` commands must be available to allow the script to check for and create the database. |
| **Project Structure** | The script must be executed from the project root directory (where `manage.py` and `requirements.txt` are located). |
| **Permissions** | The script uses `sudo` for setting up the log directory (`/opt/ritapi-v-sentinel/logs`) ownership/permissions (`www-data`). |

## 🚀 Installation and Quick Start

The provided script, typically named `setup.sh`, automates the entire installation, configuration, and launch process.

### 1. Make the Script Executable

First, ensure the script file has execution rights:

```bash
chmod +x setup.sh