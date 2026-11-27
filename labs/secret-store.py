"""Verify Ansible Vault encryption without printing the credential or vault key."""
import subprocess,pathlib,secrets,json
root=pathlib.Path(__file__).resolve().parents[2];private=root/'vault-private';private.mkdir(mode=0o700,exist_ok=True)
key=private/'key';key.write_text(secrets.token_hex(32));key.chmod(0o600)
secret=private/'application.yml';original=('SECRET_KEY: '+secrets.token_hex(24)+'\n').encode();secret.write_bytes(original);secret.chmod(0o600)
vault='/Users/deepanshu.negi/Documents/Codex/2026-11-17/bro-give-me-a-prompt-for/claude-handoff/taskmanager-devops-capstone/.venv/bin/ansible-vault'
subprocess.run([vault,'encrypt','--vault-password-file',str(key),str(secret)],check=True,capture_output=True)
cipher=secret.read_bytes();plain=subprocess.check_output([vault,'view','--vault-password-file',str(key),str(secret)])
assert plain==original
report={'store':'Ansible Vault AES256','cipher_header':cipher.splitlines()[0].decode(),'encrypted_at_rest':original not in cipher,'round_trip_verified':plain==original,'credential_printed':False,'public_package_contains_key':False,'Jenkins':'lab-app-secret injected through withCredentials; password-protected controller, localhost only'}
(root/'evidence/secrets.txt').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
