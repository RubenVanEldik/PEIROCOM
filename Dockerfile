# Indicate the Gurobi reference image
FROM gurobi/python:9.5.2

# Set the application directory
WORKDIR /app

# Set the build time environment variables
ARG INPUT_DATA_URL

# Install the application dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code
COPY . /app

# Download and unzip the bidding zone and interconnection data
RUN mkdir "/app/input/bidding_zones"
RUN mkdir "/app/input/bidding_zones/2025" && cd "$_" && wget "${INPUT_DATA_URL}/bidding_zones/2025.zip" && unzip "*.zip"
RUN mkdir "/app/input/bidding_zones/2030" && cd "$_" && wget "${INPUT_DATA_URL}/bidding_zones/2030.zip" && unzip "*.zip"
RUN mkdir "/app/input/interconnections"
RUN mkdir "/app/input/interconnections/2025" && cd "$_" && wget "${INPUT_DATA_URL}/interconnections/2025.zip" && unzip "*.zip"
RUN mkdir "/app/input/interconnections/2030" && cd "$_" && wget "${INPUT_DATA_URL}/interconnections/2030.zip" && unzip "*.zip"

# Command used to start the application
ENTRYPOINT ["streamlit", "run", "🌤️_Introduction.py"]
