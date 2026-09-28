# Best practices

- Quote paths and use `--` for commands that accept it.
- Validate arguments before deriving paths or changing state.
- Stage output in the destination filesystem; verify it before an atomic rename.
- Use unique snapshot names and a lock for scheduled operations.
- Keep private data, credentials, pcap files, and archives outside the repository.
- Treat `.env.example` as documentation. Export variables or load a trusted local `.env` before running a script; scripts do not execute configuration files automatically.
- Record reproduction steps in `debugging/` only when an investigation warrants a durable note. Keep disposable output in ignored `cache/`.
