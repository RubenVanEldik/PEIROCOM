# Build the Docker image
docker image rm peirocom
docker build . -t peirocom

# Build the Docker container and zip it up
docker rm peirocom-container
docker create --name peirocom-container peirocom
docker export peirocom-container | gzip > peirocom.tar.gz
