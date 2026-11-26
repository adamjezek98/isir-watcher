"""Management script for ISIR Watcher - add, remove, list entities."""

import sys
import argparse
from src.database import SessionLocal, init_db
from src.models import WatchedEntity


def add_entity(name: str, isir_id: str):
    """Add a new entity to watch."""
    db = SessionLocal()
    try:
        # Check if entity already exists
        existing = db.query(WatchedEntity).filter_by(isir_id=isir_id).first()
        if existing:
            print(f"Entity with ISIR ID '{isir_id}' already exists: {existing.name}")
            return
        
        # Create new entity
        entity = WatchedEntity(
            name=name,
            isir_id=isir_id
        )
        
        db.add(entity)
        db.commit()
        
        print(f"Successfully added entity: {name} (ISIR ID: {isir_id})")
        
    except Exception as e:
        print(f"Error adding entity: {e}")
        db.rollback()
    finally:
        db.close()


def remove_entity(isir_id: str):
    """Remove an entity from watching."""
    db = SessionLocal()
    try:
        entity = db.query(WatchedEntity).filter_by(isir_id=isir_id).first()
        
        if not entity:
            print(f"Entity with ISIR ID '{isir_id}' not found")
            return
        
        name = entity.name
        db.delete(entity)
        db.commit()
        
        print(f"Successfully removed entity: {name} (ISIR ID: {isir_id})")
        
    except Exception as e:
        print(f"Error removing entity: {e}")
        db.rollback()
    finally:
        db.close()


def list_entities():
    """List all watched entities."""
    db = SessionLocal()
    try:
        entities = db.query(WatchedEntity).all()
        
        if not entities:
            print("No entities being watched")
            return
        
        print(f"\n{'ID':<5} {'Name':<30} {'ISIR ID':<40} {'Last Checked':<20}")
        print("-" * 100)
        
        for entity in entities:
            last_checked = entity.last_checked.strftime('%Y-%m-%d %H:%M:%S') if entity.last_checked else 'Never'
            print(f"{entity.id:<5} {entity.name:<30} {entity.isir_id:<40} {last_checked:<20}")
        
        print(f"\nTotal: {len(entities)} entities")
        
    except Exception as e:
        print(f"Error listing entities: {e}")
    finally:
        db.close()


def show_entity_details(isir_id: str):
    """Show detailed information about an entity and its documents."""
    db = SessionLocal()
    try:
        entity = db.query(WatchedEntity).filter_by(isir_id=isir_id).first()
        
        if not entity:
            print(f"Entity with ISIR ID '{isir_id}' not found")
            return
        
        print(f"\nEntity: {entity.name}")
        print(f"ISIR ID: {entity.isir_id}")
        print(f"Last Checked: {entity.last_checked}")
        print(f"Last Modified: {entity.last_modified}")
        print(f"Consecutive Invalid-Link Failures: {entity.consecutive_failures}")
        
        # Count documents by type
        print(f"\nDocuments:")
        print(f"  Before Bankruptcy: {len(entity.before_bankruptcy_docs)} ({sum(1 for d in entity.before_bankruptcy_docs if d.is_deleted)} deleted)")
        print(f"  After Bankruptcy: {len(entity.after_bankruptcy_docs)} ({sum(1 for d in entity.after_bankruptcy_docs if d.is_deleted)} deleted)")
        print(f"  Other: {len(entity.other_docs)} ({sum(1 for d in entity.other_docs if d.is_deleted)} deleted)")
        print(f"  Applications: {len(entity.application_docs)} ({sum(1 for d in entity.application_docs if d.is_deleted)} deleted)")
        print(f"  Disputes: {len(entity.dispute_docs)} ({sum(1 for d in entity.dispute_docs if d.is_deleted)} deleted)")
        
        total = (len(entity.before_bankruptcy_docs) + len(entity.after_bankruptcy_docs) + 
                len(entity.other_docs) + len(entity.application_docs) + len(entity.dispute_docs))
        print(f"\nTotal: {total} documents")
        
    except Exception as e:
        print(f"Error showing entity details: {e}")
    finally:
        db.close()


def main():
    """Main entry point for management script."""
    parser = argparse.ArgumentParser(description='ISIR Watcher Management Tool')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Add entity command
    add_parser = subparsers.add_parser('add', help='Add a new entity to watch')
    add_parser.add_argument('name', help='Entity name')
    add_parser.add_argument('isir_id', help='ISIR entity ID')
    
    # Remove entity command
    remove_parser = subparsers.add_parser('remove', help='Remove an entity from watching')
    remove_parser.add_argument('isir_id', help='ISIR entity ID')
    
    # List entities command
    list_parser = subparsers.add_parser('list', help='List all watched entities')
    
    # Show entity details command
    show_parser = subparsers.add_parser('show', help='Show entity details')
    show_parser.add_argument('isir_id', help='ISIR entity ID')
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    # Execute command
    if args.command == 'add':
        add_entity(args.name, args.isir_id)
    elif args.command == 'remove':
        remove_entity(args.isir_id)
    elif args.command == 'list':
        list_entities()
    elif args.command == 'show':
        show_entity_details(args.isir_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

