"""runs migrations and collects static files"""
from django.core.management import call_command

def main():
    print("Making migrations...")
    call_command("makemigrations")
    print("Running migrations...")
    call_command("migrate", "--noinput")
    print("Collecting static files...")
    call_command("collectstatic", "--noinput", "--clear")

if __name__ == "__main__":
    main()