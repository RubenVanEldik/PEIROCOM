docker rm peirocom-container
docker create --name peirocom-container peirocom
docker export peirocom-container | gzip > peirocom.tar.gz
