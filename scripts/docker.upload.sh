echo "Username:"
read user_id

echo "IP address:"
read server

cd ..
scp .env $user_id@$server:Documents
scp gurobi.lic $user_id@$server:Documents
scp peirocom.tar.gz $user_id@$server:Documents
scp -r scripts $user_id@$server:Documents
