up:
	cd frontend && pnpm build && cd ../
	newgrp docker
	docker compose -f docker-compose.yml -f docker-compose.prod.yml --project-name prod up -d --build