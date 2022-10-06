cd ..
docker rm thesis-model-container
docker create --name thesis-model-container thesis-model
docker export thesis-model-container | gzip > thesis-model.tar.gz
