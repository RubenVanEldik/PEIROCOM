cd ..
docker container stop peirocom-container
docker rm peirocom-container
docker image rm thesis-model
zcat thesis-model.tar.gz | docker import -c "WORKDIR /app" -c "CMD streamlit run 🌤️_Introduction.py" - thesis-model
