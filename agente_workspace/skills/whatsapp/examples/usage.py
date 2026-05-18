"""Basic usage example for the WhatsApp skill in OpenClaw."""

from skills.whatsapp.whatsapp_skill import WhatsAppSkill


def main() -> None:
    skill = WhatsAppSkill()
    skill.run(skip_llm=True)


if __name__ == "__main__":
    main()
