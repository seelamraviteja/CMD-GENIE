# My commands

Your personal command cheat-sheet. Edit this file freely — the assistant reads
it on every question and prefers your commands over general knowledge.

Format: one command per bullet, as `` `the command` `` followed by — a short note.

## git

- `git status` — show the working tree status
- `git switch -c <branch>` — create and switch to a new branch
- `git commit --amend --no-edit` — fold staged changes into the last commit, keep its message
- `git reset --soft HEAD~1` — undo the last commit but keep the changes staged
- `git restore --staged <file>` — unstage a file (keep its changes)
- `git restore <file>` — discard uncommitted changes to a file
- `git push --force-with-lease` — force push safely (won't clobber others' work)
- `git log --oneline --graph --all` — compact visual history of all branches
- `git stash` / `git stash pop` — shelve and restore uncommitted changes
- `git rebase -i HEAD~3` — interactively edit the last 3 commits
- `git cherry-pick <sha>` — apply a single commit onto the current branch
- `git fetch --prune` — update remotes and drop deleted remote branches
- `git diff --staged` — see what's staged for commit
- `git remote -v` — list configured remotes

## docker

- `docker ps` — list running containers
- `docker ps -a` — list all containers (incl. stopped)
- `docker build -t <name> .` — build an image from the local Dockerfile
- `docker run -p 8080:8080 <name>` — run an image, mapping a port
- `docker exec -it <container> bash` — open a shell inside a running container
- `docker logs -f <container>` — follow a container's logs
- `docker compose up -d` — start services in the background
- `docker system prune -af` — remove all unused images, containers, and networks

## linux

- `tar -czf out.tar.gz <dir>` — compress a folder to a .tar.gz
- `tar -xzf out.tar.gz` — extract a .tar.gz
- `grep -rn "<text>" .` — recursively search for text, with line numbers
- `find . -name "*.log" -delete` — find and delete files by pattern
- `du -sh *` — size of each item in the current directory
- `lsof -i :8080` — find which process is using a port
- `kill -9 <pid>` — force-kill a process by id
- `chmod +x <file>` — make a file executable

## ssh

- `ssh-keygen -t ed25519 -C "you@email"` — generate a new SSH key
- `cat ~/.ssh/id_ed25519.pub` — print your public key (to add to GitHub)
- `ssh -T git@github.com` — test your GitHub SSH connection

## python / uv

- `uv venv` — create a virtual environment
- `uv sync` — install dependencies from pyproject
- `uv run <cmd>` — run a command inside the project environment
- `uv add <package>` — add a dependency

## node / npm

- `npm ci` — clean install from package-lock.json
- `npm run build` — run the build script
- `npx <tool>` — run a package binary without installing it globally
