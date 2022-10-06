cd ..
docker container stop peirocom-container
docker rm peirocom-container
docker image rm peirocom
zcat peirocom.tar.gz | docker import -c "WORKDIR /app" -c "CMD streamlit run 🌤️_Introduction.py" - peirocom
