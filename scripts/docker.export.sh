cd ..
docker rm peirocom-container
docker create --name peirocom-container thesis-model
docker export peirocom-container | gzip > thesis-model.tar.gz
