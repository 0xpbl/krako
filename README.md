# Krako

the Quantum Experimental Laboratories at 0xpblab — directory

A web1-style directory of interesting places on the internet.

This is a project for the **Gemini protocol** — a Gemini site.

## Building the Gemini Capsule

To generate the static Gemini capsule from the source files:

```bash
python3 build_capsule.py
```

Or on Windows:

```bash
python build_capsule.py
```

This will create a `capsule/` directory with all `.gmi` files ready to be served by a Gemini server.



### Notes on TLS

- Agate will generate self-signed certificates in `.certificates/` directory on first run
- For production, use valid TLS certificates
- Gemini protocol uses port 1965 by default
- Requires TLS 1.2+ support
- The self-signed certificate will trigger a warning in Gemini clients; you can accept it for local testing

## Structure

- `dir/files/` - Source files (.txt and .md)
- `capsule/` - Generated Gemini capsule (output)
- `build_capsule.py` - Build script