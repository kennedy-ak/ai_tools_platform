# AI Tools Platform

A Django-based platform that provides various AI-powered tools including document chat, CV reviewing, and quiz generation capabilities.

## Features

- Document Chat: Interactive chat interface for document analysis
- CV Reviewer: AI-powered CV analysis and feedback
- Quiz Generator: Automated quiz generation system
- User Authentication System
- Modern Web Interface

## Tech Stack

- **Backend**: Django 5.2
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **AI/ML**: 
  - LangChain
  - Transformers
  - Sentence Transformers
  - PyTorch
- **Frontend**: Django Templates
- **Deployment**: Docker support included

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Virtual environment (recommended)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai_tools_platform
```

2. Create and activate a virtual environment:
```bash
python -m venv env
# On Windows
env\Scripts\activate
# On Unix or MacOS
source env/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory and add necessary environment variables:
```
SECRET_KEY=your_secret_key
DEBUG=True
DATABASE_URL=your_database_url
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create a superuser:
```bash
python manage.py createsuperuser
```

7. Run the development server:
```bash
python manage.py runserver
```

## Project Structure

```
ai_tools_platform/
├── accounts/           # User authentication and management
├── document_chat/      # Document chat functionality
├── cv_reviewer/        # CV review system
├── quiz_generator/     # Quiz generation system
├── ai_tools_platform/  # Main project settings
├── static/            # Static files
├── templates/         # HTML templates
├── media/            # User-uploaded files
└── manage.py         # Django management script
```

## Docker Support

The project includes Docker support for containerized deployment. To run with Docker:

1. Build the Docker image:
```bash
docker build -t ai-tools-platform .
```

2. Run the container:
```bash
docker run -p 8000:8000 ai-tools-platform
```

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Make your changes
4. Submit a pull request

## License

[Add your license information here]

## Contact

[Add your contact information here] 