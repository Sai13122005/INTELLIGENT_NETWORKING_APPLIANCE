"""
MPLS Orchestrator

Coordinates LabelManager, LSPManager and
MPLSForwardingManager to manage complete MPLS LSP lifecycles.
"""

from appliance.mpls.label_manager import LabelManager
from appliance.mpls.lsp_manager import LSPManager
from appliance.mpls.forwarding import MPLSForwardingManager


class MPLSOrchestrator:

    def __init__(
        self,
        label_manager=None,
        lsp_manager=None,
        forwarding_manager=None
    ):
        # Use one shared label manager across all MPLS components.
        self.label_manager = label_manager or LabelManager()

        self.lsp_manager = lsp_manager or LSPManager(
            self.label_manager
        )

        self.forwarding_manager = (
            forwarding_manager or MPLSForwardingManager(
                self.label_manager
            )
        )

        print("[MPLS ORCHESTRATOR] Initialized successfully")

    def create_lsp(
        self,
        lsp_id,
        source,
        destination,
        path,
        source_ip,
        destination_ip
    ):
        """
        Create, install and activate an MPLS LSP.

        Workflow:
        1. Create LSP and allocate primary label.
        2. Install PUSH, SWAP and POP forwarding rules.
        3. Activate LSP.
        4. Roll back resources if any step fails.
        """

        lsp_created = False

        try:
            print(
                "\n[MPLS ORCHESTRATOR] Starting LSP creation: {}".format(
                    lsp_id
                )
            )

            # Step 1: Create LSP.
            lsp = self.lsp_manager.create_lsp(
                lsp_id,
                source,
                destination,
                path
            )

            lsp_created = True

            # Step 2: Install forwarding rules.
            installation = self.forwarding_manager.install_lsp(
                lsp,
                source_ip,
                destination_ip
            )

            if not installation:
                raise RuntimeError(
                    "MPLS forwarding installation failed."
                )

            # Step 3: Activate only after successful installation.
            activated = self.lsp_manager.activate_lsp(lsp_id)

            if not activated:
                raise RuntimeError(
                    "Could not activate LSP {}.".format(lsp_id)
                )

            print(
                "[MPLS ORCHESTRATOR] LSP {} created and activated "
                "successfully".format(lsp_id)
            )

            return {
                "success": True,
                "lsp_id": lsp_id,
                "lsp": self.lsp_manager.get_lsp(lsp_id),
                "installation": installation
            }

        except Exception as error:

            print(
                "[MPLS ORCHESTRATOR] LSP creation failed: {}".format(
                    error
                )
            )

            cleanup_errors = []

            # Remove forwarding if installation was recorded.
            try:
                existing_installation = (
                    self.forwarding_manager.get_installation(lsp_id)
                )

                if existing_installation is not None:
                    self.forwarding_manager.remove_lsp(lsp_id)

            except Exception as cleanup_error:
                cleanup_errors.append(
                    "Forwarding cleanup: {}".format(cleanup_error)
                )

            # Delete LSP and release its primary label only if
            # forwarding cleanup was successful.
            if lsp_created:
                try:
                    if self.forwarding_manager.get_installation(
                        lsp_id
                    ) is None:
                        self.lsp_manager.delete_lsp(lsp_id)

                except Exception as cleanup_error:
                    cleanup_errors.append(
                        "LSP cleanup: {}".format(cleanup_error)
                    )

            message = str(error)

            if cleanup_errors:
                message += " | Cleanup errors: " + "; ".join(
                    cleanup_errors
                )

            raise RuntimeError(message) from error

    def remove_lsp(self, lsp_id):
        """
        Deactivate and remove an LSP.

        Forwarding rules are removed before the primary label
        is released.
        """

        lsp = self.lsp_manager.get_lsp(lsp_id)

        if lsp is None:
            print(
                "[MPLS ORCHESTRATOR] LSP {} not found".format(lsp_id)
            )
            return False

        print(
            "\n[MPLS ORCHESTRATOR] Removing LSP: {}".format(lsp_id)
        )

        # Step 1: Mark LSP down.
        self.lsp_manager.deactivate_lsp(lsp_id)

        # Step 2: Remove forwarding rules and additional labels.
        # If this fails, retain the LSP and primary label.
        self.forwarding_manager.remove_lsp(lsp_id)

        # Step 3: Delete LSP and release primary label.
        deleted = self.lsp_manager.delete_lsp(lsp_id)

        if deleted:
            print(
                "[MPLS ORCHESTRATOR] LSP {} removed successfully".format(
                    lsp_id
                )
            )

        return deleted

    def get_lsp(self, lsp_id):
        """Retrieve information about an LSP."""

        return self.lsp_manager.get_lsp(lsp_id)

    def display_status(self):
        """Display current MPLS resources."""

        print("\n========== MPLS ORCHESTRATOR STATUS ==========")

        print("\n--- Label Database ---")
        self.label_manager.display_labels()

        print("\n--- LSP Database ---")
        self.lsp_manager.display_lsps()

        print("\n--- Forwarding Database ---")
        self.forwarding_manager.display_installations()

        print("==============================================")
