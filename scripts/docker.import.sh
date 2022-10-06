cd ..
docker container stop thesis-model-container
docker rm thesis-model-container
docker image rm thesis-model
zcat thesis-model.tar.gz | docker import -c "WORKDIR /app" -c "CMD streamlit run 🌤️_Introduction.py" - thesis-model
