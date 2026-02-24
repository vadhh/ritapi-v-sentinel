"""Management command to display MiniFW-AI deployment state."""

import json

from django.core.management.base import BaseCommand

from minifw.services import DeploymentStateService, MiniFWService, SectorLock


class Command(BaseCommand):
    help = "Display current MiniFW-AI deployment state and service status"

    def handle(self, *args, **options):
        state = DeploymentStateService.get_state()

        self.stdout.write(self.style.HTTP_INFO("=" * 50))
        self.stdout.write(self.style.HTTP_INFO(" MiniFW-AI Deployment Status"))
        self.stdout.write(self.style.HTTP_INFO("=" * 50))

        # Protection state
        protection = state["protection_state"]
        if protection == "AI_ENHANCED_PROTECTION":
            self.stdout.write(self.style.SUCCESS(f"  Protection State : {protection}"))
        elif protection == "BASELINE_PROTECTION":
            self.stdout.write(self.style.WARNING(f"  Protection State : {protection}"))
        else:
            self.stdout.write(self.style.ERROR(f"  Protection State : {protection}"))

        # AI status
        if state["ai_enabled"]:
            self.stdout.write(self.style.SUCCESS("  AI Modules       : Active"))
        else:
            self.stdout.write("  AI Modules       : Inactive")

        # Last check
        last_check = state.get("last_state_check") or "N/A"
        self.stdout.write(f"  Last State Check : {last_check}")

        # State file health
        if state["service_unavailable"]:
            self.stdout.write(
                self.style.ERROR(
                    f'  State File       : UNAVAILABLE ({state["unavailable_reason"]})'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("  State File       : OK"))

        # Sector
        sector = SectorLock.get_sector()
        self.stdout.write(f"  Sector           : {sector}")
        self.stdout.write(f"  Sector Info      : {SectorLock.get_description()}")

        # Service status
        try:
            svc = MiniFWService.get_status()
            status_str = svc.get("status", "unknown")
            if svc.get("active"):
                self.stdout.write(
                    self.style.SUCCESS(f"  Service          : {status_str}")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"  Service          : {status_str}")
                )
        except Exception:
            self.stdout.write(self.style.ERROR("  Service          : unknown"))

        self.stdout.write(self.style.HTTP_INFO("=" * 50))

        # Raw state JSON (verbose)
        if options.get("verbosity", 1) >= 2:
            self.stdout.write("\nRaw state JSON:")
            safe = {k: v for k, v in state.items() if k != "raw"}
            self.stdout.write(json.dumps(safe, indent=2, default=str))
