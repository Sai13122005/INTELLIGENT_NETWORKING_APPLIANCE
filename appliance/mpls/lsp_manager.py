import threading
import time
from appliance.mpls.label_manager import LabelManager


class LSPManager:
    """
    Creates and maintains MPLS Label Switched Paths.

    The LSP Manager maintains path information and obtains
    MPLS labels from the Label Manager.

    It does not install forwarding rules itself.
    """

    def __init__(self, label_manager=None):
        self.label_manager = label_manager or LabelManager()

        self.lsps = {}
        self.lock = threading.Lock()

    def create_lsp(self, lsp_id, source, destination, path):
        """Create an LSP and allocate its MPLS label."""

        if not lsp_id:
            raise ValueError("LSP ID cannot be empty.")

        if source is None or destination is None:
            raise ValueError("Source and destination are required.")

        if not isinstance(path, (list, tuple)) or len(path) < 2:
            raise ValueError("LSP path must contain at least two switches.")

        if path[0] != source or path[-1] != destination:
            raise ValueError(
                "Path endpoints must match the source and destination."
            )

        if len(set(path)) != len(path):
            raise ValueError("LSP path cannot contain repeated switches.")

        with self.lock:
            if lsp_id in self.lsps:
                raise ValueError("LSP ID already exists.")

            label = self.label_manager.allocate_label(lsp_id)

            lsp = {
                "lsp_id": lsp_id,
                "source": source,
                "destination": destination,
                "path": list(path),
                "label": label,
                "status": "CREATED",
                "created_at": time.time()
            }

            self.lsps[lsp_id] = lsp

            print(
                f"[MPLS LSP MANAGER] Created {lsp_id} | "
                f"Path: {path} | Label: {label}"
            )

            return dict(lsp)

    def activate_lsp(self, lsp_id):
        """Mark an LSP as active after forwarding setup succeeds."""

        with self.lock:
            lsp = self.lsps.get(lsp_id)

            if lsp is None:
                return False

            if lsp["status"] != "CREATED":
                return False

            lsp["status"] = "ACTIVE"

            print(f"[MPLS LSP MANAGER] {lsp_id} is ACTIVE")

            return True

    def deactivate_lsp(self, lsp_id):
        """Mark an existing LSP as down."""

        with self.lock:
            lsp = self.lsps.get(lsp_id)

            if lsp is None:
                return False

            lsp["status"] = "DOWN"

            print(f"[MPLS LSP MANAGER] {lsp_id} is DOWN")

            return True

    def delete_lsp(self, lsp_id):
        """Delete an LSP and release its allocated label."""

        with self.lock:
            lsp = self.lsps.get(lsp_id)

            if lsp is None:
                return False

            self.label_manager.release_label(lsp_id)
            del self.lsps[lsp_id]

            print(f"[MPLS LSP MANAGER] Deleted {lsp_id}")

            return True

    def get_lsp(self, lsp_id):
        """Retrieve information about one LSP."""

        with self.lock:
            lsp = self.lsps.get(lsp_id)

            return dict(lsp) if lsp else None

    def get_all_lsps(self):
        """Return all currently maintained LSPs."""

        with self.lock:
            return {
                lsp_id: dict(lsp)
                for lsp_id, lsp in self.lsps.items()
            }

    def display_lsps(self):
        """Display the LSP database."""

        lsps = self.get_all_lsps()

        print("\n========== MPLS LSP DATABASE ==========")

        if not lsps:
            print("No LSPs currently configured.")

        for lsp_id, lsp in lsps.items():
            print(f"LSP ID: {lsp_id}")
            print(f"  Source:      {lsp['source']}")
            print(f"  Destination: {lsp['destination']}")
            print(f"  Path:        {' -> '.join(map(str, lsp['path']))}")
            print(f"  Label:       {lsp['label']}")
            print(f"  Status:      {lsp['status']}")
            print("---------------------------------------")

        print("=======================================\n")
