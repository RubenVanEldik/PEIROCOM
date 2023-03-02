# Remove any existing containers or images
docker container stop peirocom-container
docker rm peirocom-container

# Build and run the container
docker build . -t peirocom $(for i in `cat .env`; do out+="--build-arg $i " ; done; echo $out;out="")
docker run -p=8501:8501 --name peirocom-container peirocom
