"""
Account Manager Module
======================

This module manages multiple accounts for Flows Lab automation.
It handles account rotation, usage tracking, and authentication state.

Usage:
    manager = AccountManager(accounts_csv_path)
    account = manager.get_next_active_account()
    manager.mark_account_used(account.account_name)
"""

import csv
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from .utils import get_logger


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Account:
    """Represents a Flows Lab account."""
    account_name: str
    email: str
    password: str
    profile_dir: str = ""
    cookies_file: str = ""
    active: bool = True

    # Runtime tracking (not persisted)
    scenes_processed: int = field(default=0, repr=False)
    last_used: Optional[datetime] = field(default=None, repr=False)
    login_status: str = field(default="unknown", repr=False)  # unknown, success, failed
    error_count: int = field(default=0, repr=False)


# ============================================================================
# AccountManager Class
# ============================================================================

class AccountManager:
    """
    Manages multiple Flows Lab accounts for automation.

    Features:
    - Load accounts from CSV file
    - Round-robin account selection
    - Usage tracking per session
    - Account rotation when limits are reached

    Attributes:
        csv_path: Path to the accounts CSV file.
        accounts: List of Account objects.
        current_index: Index of currently selected account.
        max_scenes_per_account: Maximum scenes to process per account.
        logger: Logger instance.
    """

    def __init__(
        self,
        csv_path: Path,
        max_scenes_per_account: int = 50,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the AccountManager.

        Args:
            csv_path: Path to the accounts CSV file.
            max_scenes_per_account: Max scenes before rotating accounts.
            logger: Optional logger instance.
        """
        self.csv_path = Path(csv_path)
        self.accounts: list[Account] = []
        self.current_index: int = 0
        self.max_scenes_per_account = max_scenes_per_account
        self.logger = logger or get_logger("ve3_tool.account_manager")

        self._load_accounts()

    def _load_accounts(self) -> None:
        """
        Load accounts from CSV file.

        Raises:
            FileNotFoundError: If CSV file doesn't exist.
            ValueError: If CSV format is invalid.
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Accounts file not found: {self.csv_path}\n"
                f"Please create a CSV file with columns: "
                f"account_name, email, password, profile_dir, cookies_file, active"
            )

        self.accounts = []

        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            # Validate required columns
            required_cols = {'account_name', 'email', 'password'}
            if not reader.fieldnames:
                raise ValueError("Empty CSV file or no headers found")

            missing_cols = required_cols - set(reader.fieldnames)
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")

            for row in reader:
                # Parse 'active' field
                active_str = row.get('active', 'true').lower().strip()
                is_active = active_str in ('true', '1', 'yes', 'y')

                account = Account(
                    account_name=row.get('account_name', '').strip(),
                    email=row.get('email', '').strip(),
                    password=row.get('password', '').strip(),
                    profile_dir=row.get('profile_dir', '').strip(),
                    cookies_file=row.get('cookies_file', '').strip(),
                    active=is_active
                )

                # Skip entries without required fields
                if account.account_name and account.email:
                    self.accounts.append(account)

        active_count = sum(1 for a in self.accounts if a.active)
        self.logger.info(
            f"Loaded {len(self.accounts)} accounts "
            f"({active_count} active) from {self.csv_path.name}"
        )

    def get_active_accounts(self) -> list[Account]:
        """
        Get list of active accounts.

        Returns:
            List of Account objects where active=True.
        """
        return [a for a in self.accounts if a.active]

    def get_account_by_name(self, name: str) -> Optional[Account]:
        """
        Get account by name.

        Args:
            name: Account name to find.

        Returns:
            Account object or None if not found.
        """
        for account in self.accounts:
            if account.account_name == name:
                return account
        return None

    def get_next_active_account(self) -> Optional[Account]:
        """
        Get the next available active account using round-robin selection.

        This method considers:
        - Account must be active
        - Account must not have exceeded scene limit
        - Account must not have too many errors

        Returns:
            Next available Account, or None if all accounts exhausted.
        """
        active_accounts = self.get_active_accounts()

        if not active_accounts:
            self.logger.error("No active accounts available")
            return None

        # Try each account starting from current index
        attempts = 0
        while attempts < len(active_accounts):
            account = active_accounts[self.current_index % len(active_accounts)]
            self.current_index += 1

            # Check if account is usable
            if self._is_account_usable(account):
                self.logger.debug(f"Selected account: {account.account_name}")
                return account

            attempts += 1

        self.logger.warning("All accounts exhausted or have errors")
        return None

    def _is_account_usable(self, account: Account) -> bool:
        """
        Check if an account is currently usable.

        Args:
            account: Account to check.

        Returns:
            True if account can be used.
        """
        if not account.active:
            return False

        if account.scenes_processed >= self.max_scenes_per_account:
            self.logger.debug(
                f"Account {account.account_name} reached scene limit "
                f"({account.scenes_processed}/{self.max_scenes_per_account})"
            )
            return False

        if account.error_count >= 3:
            self.logger.debug(
                f"Account {account.account_name} has too many errors "
                f"({account.error_count})"
            )
            return False

        if account.login_status == "failed":
            return False

        return True

    def mark_account_used(
        self,
        account_name: str,
        scenes: int = 1
    ) -> None:
        """
        Mark account as used (increment scene counter).

        Args:
            account_name: Name of the account.
            scenes: Number of scenes processed (default 1).
        """
        account = self.get_account_by_name(account_name)
        if account:
            account.scenes_processed += scenes
            account.last_used = datetime.now()
            self.logger.debug(
                f"Account {account_name}: {account.scenes_processed} scenes processed"
            )

    def mark_account_error(
        self,
        account_name: str,
        error_msg: str = ""
    ) -> None:
        """
        Mark account as having an error.

        Args:
            account_name: Name of the account.
            error_msg: Optional error message for logging.
        """
        account = self.get_account_by_name(account_name)
        if account:
            account.error_count += 1
            self.logger.warning(
                f"Account {account_name} error #{account.error_count}: {error_msg}"
            )

    def mark_login_status(
        self,
        account_name: str,
        success: bool
    ) -> None:
        """
        Mark account login status.

        Args:
            account_name: Name of the account.
            success: Whether login was successful.
        """
        account = self.get_account_by_name(account_name)
        if account:
            account.login_status = "success" if success else "failed"
            self.logger.info(
                f"Account {account_name} login: "
                f"{'successful' if success else 'failed'}"
            )

    def reset_session_counters(self) -> None:
        """Reset all session-related counters for all accounts."""
        for account in self.accounts:
            account.scenes_processed = 0
            account.error_count = 0
            account.login_status = "unknown"
            account.last_used = None

        self.current_index = 0
        self.logger.info("Reset session counters for all accounts")

    def get_status_summary(self) -> dict:
        """
        Get summary of account statuses.

        Returns:
            Dictionary with status summary.
        """
        active = [a for a in self.accounts if a.active]
        return {
            "total_accounts": len(self.accounts),
            "active_accounts": len(active),
            "usable_accounts": sum(1 for a in active if self._is_account_usable(a)),
            "scenes_processed_total": sum(a.scenes_processed for a in self.accounts),
            "accounts_with_errors": sum(1 for a in self.accounts if a.error_count > 0),
            "accounts_login_failed": sum(
                1 for a in self.accounts if a.login_status == "failed"
            ),
        }

    def print_status(self) -> None:
        """Print account status to console."""
        print("\n" + "=" * 60)
        print("ACCOUNT STATUS")
        print("=" * 60)

        for account in self.accounts:
            status_icon = "✓" if account.active else "✗"
            login_icon = {
                "success": "🟢",
                "failed": "🔴",
                "unknown": "⚪"
            }.get(account.login_status, "⚪")

            print(
                f"{status_icon} {account.account_name:20} | "
                f"Scenes: {account.scenes_processed:3} | "
                f"Errors: {account.error_count} | "
                f"Login: {login_icon}"
            )

        summary = self.get_status_summary()
        print("-" * 60)
        print(
            f"Total: {summary['active_accounts']}/{summary['total_accounts']} active | "
            f"{summary['usable_accounts']} usable | "
            f"{summary['scenes_processed_total']} scenes processed"
        )
        print("=" * 60 + "\n")


# ============================================================================
# Utility Functions
# ============================================================================

def create_sample_accounts_csv(path: Path) -> None:
    """
    Create a sample accounts CSV file.

    Args:
        path: Path where to create the file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'account_name', 'email', 'password',
            'profile_dir', 'cookies_file', 'active'
        ])
        writer.writerow([
            'account_01', 'your_email@example.com', 'your_password',
            '', '', 'true'
        ])

    print(f"Created sample accounts file: {path}")
    print("Please edit this file with your actual account credentials.")
