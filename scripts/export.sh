# Remove the existing container and image
docker rm peirocom-container
docker image rm peirocom

# Build the Docker image
docker build . -t peirocom

# Build the Docker container and zip it up
docker create --name peirocom-container peirocom
docker export peirocom-container | gzip > peirocom.tar.gz
