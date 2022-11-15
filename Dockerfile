# Indicate the Gurobi reference image
FROM gurobi/python:9.5.2

# Set the application directory
WORKDIR /app

# Install the application dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code
COPY . /app

# Command used to start the application
ENTRYPOINT ["streamlit", "run", "🌤️_Introduction.py"]
