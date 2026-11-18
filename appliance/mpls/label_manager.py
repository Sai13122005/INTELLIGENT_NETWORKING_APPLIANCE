import threading


class LabelManager:
    """
    Manages MPLS label allocation and release.

    This is a software-based label allocator.
    Labels are assigned to LSP identifiers.
    """

    def __init__(self, start_label=100, end_label=1048575):
        if start_label < 16:
            raise ValueError("Labels below 16 are reserved.")

        if end_label < start_label or end_label > 1048575:
            raise ValueError("Invalid MPLS label range.")

        self.start_label = start_label
        self.end_label = end_label

        self.allocated_labels = {}
        self.lsp_to_label = {}

        self.next_label = start_label
        self.lock = threading.Lock()

    def allocate_label(self, lsp_id):
        """Allocate a unique label for an LSP."""

        if not lsp_id:
            raise ValueError("LSP ID cannot be empty.")

        with self.lock:
            if lsp_id in self.lsp_to_label:
                return self.lsp_to_label[lsp_id]

            total_labels = self.end_label - self.start_label + 1

            for _ in range(total_labels):
                label = self.next_label

                self.next_label += 1

                if self.next_label > self.end_label:
                    self.next_label = self.start_label

                if label not in self.allocated_labels:
                    self.allocated_labels[label] = {
                        "lsp_id": lsp_id,
                        "status": "IN_USE"
                    }

                    self.lsp_to_label[lsp_id] = label

                    print(
                        f"[MPLS LABEL MANAGER] "
                        f"Allocated label {label} to {lsp_id}"
                    )

                    return label

            raise RuntimeError("No MPLS labels available.")

    def release_label(self, lsp_id):
        """Release the label assigned to an LSP."""

        with self.lock:
            label = self.lsp_to_label.get(lsp_id)

            if label is None:
                print(
                    f"[MPLS LABEL MANAGER] "
                    f"No label found for {lsp_id}"
                )
                return False

            del self.allocated_labels[label]
            del self.lsp_to_label[lsp_id]

            print(
                f"[MPLS LABEL MANAGER] "
                f"Released label {label} from {lsp_id}"
            )

            return True

    def get_label(self, lsp_id):
        """Return the label assigned to an LSP."""

        with self.lock:
            return self.lsp_to_label.get(lsp_id)

    def get_label_details(self, label):
        """Return information about an allocated label."""

        with self.lock:
            details = self.allocated_labels.get(label)

            return dict(details) if details else None

    def get_all_labels(self):
        """Return a copy of all allocated labels."""

        with self.lock:
            return {
                label: dict(details)
                for label, details in self.allocated_labels.items()
            }

    def display_labels(self):
        """Display all currently allocated labels."""

        labels = self.get_all_labels()

        print("\n========== MPLS LABEL DATABASE ==========")

        if not labels:
            print("No labels currently allocated.")

        for label, details in sorted(labels.items()):
            print(
                f"Label: {label} | "
                f"LSP: {details['lsp_id']} | "
                f"Status: {details['status']}"
            )

        print("=========================================\n")
