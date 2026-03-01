#!/usr/bin/env python3
"""
Environment Manager - Phase 2 Task G
Manages different environments (dev, staging, production)
"""

import json
import yaml
from typing import Dict, List, Optional
from pathlib import Path


class EnvManager:
    """
    Manages environments like Postman does.
    
    Supports:
    - Multiple environments (dev, staging, prod)
    - Environment switching
    - Variable management
    - Safe production mode
    """
    
    def __init__(self, config_dir: str = ".ai-test"):
        self.config_dir = Path(config_dir)
        self.environments_dir = self.config_dir / "environments"
        self.active_env_file = self.config_dir / "active_env.txt"
        
        # Ensure directories exist
        self.environments_dir.mkdir(parents=True, exist_ok=True)
    
    def create_env(self, name: str, base_url: str, variables: Dict[str, str] = None) -> str:
        """
        Create a new environment.
        
        Args:
            name: Environment name (dev, staging, prod, etc.)
            base_url: Base URL for this environment
            variables: Additional environment variables
            
        Returns:
            Path to created environment file
        """
        env_data = {
            'name': name.title(),
            'base_url': base_url,
            'variables': variables or {},
            'read_only': name.lower() == 'production' or name.lower() == 'prod',
            'created_at': str(Path.cwd())
        }
        
        if env_data['read_only']:
            env_data['warning'] = "⚠️  PRODUCTION ENVIRONMENT - Use with caution!"
        
        env_file = self.environments_dir / f"{name.lower()}.yaml"
        
        with open(env_file, 'w') as f:
            yaml.dump(env_data, f, default_flow_style=False)
        
        print(f"✓ Created environment: {name}")
        print(f"  File: {env_file}")
        
        return str(env_file)
    
    def list_envs(self) -> List[str]:
        """
        List all available environments.
        
        Returns:
            List of environment names
        """
        if not self.environments_dir.exists():
            return []
        
        env_files = list(self.environments_dir.glob("*.yaml")) + \
                   list(self.environments_dir.glob("*.yml"))
        
        return [f.stem for f in env_files]
    
    def use_env(self, name: str) -> bool:
        """
        Switch to a different environment.
        
        Args:
            name: Environment name to switch to
            
        Returns:
            True if switched successfully
        """
        env_file = self.environments_dir / f"{name.lower()}.yaml"
        
        if not env_file.exists():
            # Try .yml extension
            env_file = self.environments_dir / f"{name.lower()}.yml"
            if not env_file.exists():
                print(f"❌ Environment '{name}' not found")
                print(f"   Available: {', '.join(self.list_envs())}")
                return False
        
        # Load environment to check for warnings
        with open(env_file, 'r') as f:
            env_data = yaml.safe_load(f)
        
        # Warn if production
        if env_data.get('read_only'):
            print(f"\n⚠️  WARNING: Switching to {env_data['name']} environment!")
            print("   This is a READ-ONLY environment.")
            print("   Destructive tests will be blocked.\n")
        
        # Set as active
        with open(self.active_env_file, 'w') as f:
            f.write(name.lower())
        
        print(f"✓ Switched to environment: {env_data['name']}")
        
        # Update .env file
        self._update_env_file(env_data)
        
        return True
    
    def get_active_env(self) -> Optional[Dict]:
        """
        Get currently active environment.
        
        Returns:
            Environment data dict or None
        """
        if not self.active_env_file.exists():
            return None
        
        with open(self.active_env_file, 'r') as f:
            env_name = f.read().strip()
        
        return self.get_env(env_name)
    
    def get_env(self, name: str) -> Optional[Dict]:
        """
        Get environment data by name.
        
        Args:
            name: Environment name
            
        Returns:
            Environment data dict or None
        """
        env_file = self.environments_dir / f"{name.lower()}.yaml"
        
        if not env_file.exists():
            env_file = self.environments_dir / f"{name.lower()}.yml"
            if not env_file.exists():
                return None
        
        with open(env_file, 'r') as f:
            return yaml.safe_load(f)
    
    def set_variable(self, key: str, value: str, env_name: Optional[str] = None) -> bool:
        """
        Set a variable in an environment.
        
        Args:
            key: Variable key
            value: Variable value
            env_name: Environment name (uses active if None)
            
        Returns:
            True if set successfully
        """
        if env_name is None:
            # Use active environment
            if not self.active_env_file.exists():
                print("❌ No active environment. Use 'env use <name>' first.")
                return False
            
            with open(self.active_env_file, 'r') as f:
                env_name = f.read().strip()
        
        env_data = self.get_env(env_name)
        if not env_data:
            print(f"❌ Environment '{env_name}' not found")
            return False
        
        # Check if read-only
        if env_data.get('read_only'):
            print(f"⚠️  Environment '{env_name}' is read-only!")
            response = input("Are you sure you want to modify it? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ Cancelled")
                return False
        
        # Update variable
        if 'variables' not in env_data:
            env_data['variables'] = {}
        
        env_data['variables'][key] = value
        
        # Save
        env_file = self.environments_dir / f"{env_name.lower()}.yaml"
        with open(env_file, 'w') as f:
            yaml.dump(env_data, f, default_flow_style=False)
        
        print(f"✓ Set {key} = {value} in environment '{env_name}'")
        
        # Update .env if this is active environment
        active_env = self.get_active_env()
        if active_env and active_env['name'].lower() == env_name.lower():
            self._update_env_file(env_data)
        
        return True
    
    def show_env(self, name: Optional[str] = None) -> None:
        """
        Show environment details.
        
        Args:
            name: Environment name (uses active if None)
        """
        if name is None:
            env_data = self.get_active_env()
            if not env_data:
                print("❌ No active environment")
                print("   Use: env use <name>")
                return
        else:
            env_data = self.get_env(name)
            if not env_data:
                print(f"❌ Environment '{name}' not found")
                return
        
        print("\n" + "="*60)
        print(f"🌍 Environment: {env_data['name']}")
        print("="*60)
        
        print(f"\nBase URL: {env_data['base_url']}")
        
        if env_data.get('read_only'):
            print(f"Mode: READ-ONLY ⚠️")
        else:
            print(f"Mode: Read/Write")
        
        if env_data.get('warning'):
            print(f"\n⚠️  {env_data['warning']}")
        
        variables = env_data.get('variables', {})
        if variables:
            print(f"\nVariables ({len(variables)}):")
            for key, value in variables.items():
                # Mask sensitive values
                if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                    display_value = '*' * 8
                else:
                    display_value = value
                print(f"  {key}: {display_value}")
        else:
            print("\nVariables: None")
        
        print("="*60 + "\n")
    
    def _update_env_file(self, env_data: Dict) -> None:
        """Update .env file with environment variables."""
        env_file = Path(".env")
        
        lines = []
        lines.append(f"# Environment: {env_data['name']}")
        lines.append(f"# Updated by AI Testing Agent")
        lines.append("")
        
        # Base URL
        lines.append(f"BASE_URL={env_data['base_url']}")
        
        # Other variables
        for key, value in env_data.get('variables', {}).items():
            lines.append(f"{key}={value}")
        
        with open(env_file, 'w') as f:
            f.write('\n'.join(lines))
        
        print(f"  ✓ Updated .env file")
    
    def create_default_envs(self) -> None:
        """Create default dev/staging/prod environments."""
        print("📦 Creating default environments...")
        
        # Development
        self.create_env(
            'dev',
            'http://localhost:8000',
            {
                'TEST_EMAIL': 'dev@your-domain.com',
                'TEST_PASSWORD': 'change-me',
                'DEBUG': 'true'
            }
        )
        
        # Staging
        self.create_env(
            'staging',
            'https://staging.api.example.com',
            {
                'TEST_EMAIL': 'staging@your-domain.com',
                'TEST_PASSWORD': 'change-me',
                'DEBUG': 'false'
            }
        )
        
        # Production (read-only)
        self.create_env(
            'production',
            'https://api.example.com',
            {
                'TEST_EMAIL': 'prod@your-domain.com',
                'TEST_PASSWORD': 'change-me',
                'DEBUG': 'false'
            }
        )
        
        print("\n✓ Created 3 default environments")
        print("  Use: env use dev")
    
    def delete_env(self, name: str, force: bool = False) -> bool:
        """
        Delete an environment.
        
        Args:
            name: Environment name
            force: Skip confirmation
            
        Returns:
            True if deleted
        """
        env_file = self.environments_dir / f"{name.lower()}.yaml"
        
        if not env_file.exists():
            env_file = self.environments_dir / f"{name.lower()}.yml"
            if not env_file.exists():
                print(f"❌ Environment '{name}' not found")
                return False
        
        if not force:
            response = input(f"Delete environment '{name}'? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ Cancelled")
                return False
        
        env_file.unlink()
        print(f"✓ Deleted environment: {name}")
        
        # Clear active if this was active
        if self.active_env_file.exists():
            with open(self.active_env_file, 'r') as f:
                active = f.read().strip()
            if active.lower() == name.lower():
                self.active_env_file.unlink()
                print("  ℹ️  Cleared active environment")
        
        return True
    
    def export_env(self, name: str, output_file: str) -> bool:
        """
        Export environment to file.
        
        Args:
            name: Environment name
            output_file: Output file path
            
        Returns:
            True if exported
        """
        env_data = self.get_env(name)
        if not env_data:
            print(f"❌ Environment '{name}' not found")
            return False
        
        output_path = Path(output_file)
        
        if output_path.suffix == '.json':
            with open(output_path, 'w') as f:
                json.dump(env_data, f, indent=2)
        else:
            with open(output_path, 'w') as f:
                yaml.dump(env_data, f, default_flow_style=False)
        
        print(f"✓ Exported environment '{name}' to {output_file}")
        return True
    
    def import_env(self, input_file: str, name: Optional[str] = None) -> bool:
        """
        Import environment from file.
        
        Args:
            input_file: Input file path
            name: Environment name (uses file name if None)
            
        Returns:
            True if imported
        """
        input_path = Path(input_file)
        
        if not input_path.exists():
            print(f"❌ File not found: {input_file}")
            return False
        
        # Load data
        if input_path.suffix == '.json':
            with open(input_path, 'r') as f:
                env_data = json.load(f)
        else:
            with open(input_path, 'r') as f:
                env_data = yaml.safe_load(f)
        
        # Determine name
        env_name = name or input_path.stem
        
        # Save to environments
        env_file = self.environments_dir / f"{env_name.lower()}.yaml"
        with open(env_file, 'w') as f:
            yaml.dump(env_data, f, default_flow_style=False)
        
        print(f"✓ Imported environment: {env_name}")
        return True
