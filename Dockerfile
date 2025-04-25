# Use the official Python image as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Set environment variables
ENV DJANGO_SETTINGS_MODULE=ai_tools_platform.settings
ENV DEBUG=False

# Expose the port the app runs on
EXPOSE 8080

# Run the application
CMD ["python manage.py runserver"]
