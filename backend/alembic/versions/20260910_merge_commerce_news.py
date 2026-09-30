"""Merge the platform-commerce and website-news migration heads.

Revision ID: 20260910_merge_commerce_news
Revises: 20260909_module_commerce_m8_operations, 20260909_website_news_packages

This revision only joins two independently developed histories. It performs no
schema or data operation.
"""
from __future__ import annotations


revision = "20260910_merge_commerce_news"
down_revision = (
    "20260909_module_commerce_m8_operations",
    "20260909_website_news_packages",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
