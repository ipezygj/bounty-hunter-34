.PHONY: install-hooks uninstall-hooks

install-hooks:
	@echo "Installing pre-commit hook..."
	@if [ ! -d .git ]; then \
		echo "Error: Not a git repository. Run this from the repository root."; \
		exit 1; \
	fi
	@mkdir -p .git/hooks
	@if [ -e .git/hooks/pre-commit ] && [ ! -L .git/hooks/pre-commit ]; then \
		echo "Warning: .git/hooks/pre-commit exists and is not a symlink."; \
		echo "Backing it up to .git/hooks/pre-commit.backup"; \
		mv .git/hooks/pre-commit .git/hooks/pre-commit.backup; \
	fi
	@rm -f .git/hooks/pre-commit
	@ln -s ../../tools/pre-commit .git/hooks/pre-commit
	@chmod +x tools/pre-commit
	@echo "✓ Pre-commit hook installed successfully"
	@echo ""
	@echo "The hook will now run automatically before each commit."
	@echo "To temporarily skip the hook, use: git commit --no-verify"

uninstall-hooks:
	@echo "Uninstalling pre-commit hook..."
	@if [ -L .git/hooks/pre-commit ]; then \
		rm .git/hooks/pre-commit; \
		echo "✓ Pre-commit hook uninstalled"; \
	elif [ -e .git/hooks/pre-commit ]; then \
		echo "Warning: .git/hooks/pre-commit exists but is not a symlink"; \
		echo "Remove it manually if you want to uninstall it"; \
	else \
		echo "Pre-commit hook not found"; \
	fi
