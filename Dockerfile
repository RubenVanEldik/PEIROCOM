# Indicate the Gurobi reference image
FROM gurobi/python:9.5.2

# Set the application directory
WORKDIR /app

# Set the build time environment variables
ARG INPUT_DATA_URL
ARG GUROBI_WLSACCESSID
ARG GUROBI_WLSSECRET
ARG GUROBI_LICENSEID

# Install the application dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code
COPY . /app

# Download and unzip the bidding zone and interconnection data
RUN bash scripts/docker.input.sh

# Generate the Gurobi license file
RUN bash scripts/docker.gurobi.sh

# Command used to start the application
ENTRYPOINT ["streamlit", "run", "🌤️_Introduction.py"]
