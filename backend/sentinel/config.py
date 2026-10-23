from dataclasses import dataclass
import os
import re

@dataclass(frozen=True)
class Settings:
    hosting_tier: str = os.getenv('HOSTING_TIER', 'local')
    database_expiry: str = os.getenv('DATABASE_EXPIRY', '')
    access_team: str = os.getenv('CF_ACCESS_TEAM', '')
    access_aud: str = os.getenv('CF_ACCESS_AUD', '')
    owner_email: str = os.getenv('OWNER_EMAIL', '')
    environment: str = os.getenv('ENVIRONMENT', 'development')
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///sentinel.dev.db')
    session_secret: str = os.getenv('SESSION_SECRET', '')
    password_hash: str = os.getenv('OWNER_PASSWORD_HASH', '')
    origin: str = os.getenv('APP_ORIGIN', 'http://localhost:3000')
    collect: bool = os.getenv('COLLECT_MARKETS', 'false').lower() == 'true'
    # Terms approval is separate from technical connectivity. No provider enabled implicitly.
    providers: tuple[str, ...] = tuple(p.strip() for p in os.getenv('APPROVED_PROVIDERS', '').split(',') if p.strip())
    changenow_key: str = os.getenv('CHANGENOW_API_KEY', '')
    changenow_approved: bool = os.getenv('CHANGENOW_RESEARCH_APPROVED', 'false').lower() == 'true'
    ntfy_topic: str = os.getenv('NTFY_TOPIC', '')
    ntfy_token: str = os.getenv('NTFY_TOKEN', '')

    def validate(self):
        if self.environment not in {'development', 'test', 'production', 'staging'}:
            raise ValueError('Unknown environment')
        if self.environment in {'production', 'staging'}:
            if not self.database_url.startswith(('postgres://', 'postgresql://')):
                raise ValueError('Hosted environments require dedicated PostgreSQL')
            if len(self.session_secret) < 32 or (not self.password_hash.startswith('scrypt
                raise ValueError('Configure a strong SESSION_SECRET and owner password or verified Cloudflare Access before hosting')
            if not self.origin.startswith('https://'):
                raise ValueError('Hosted origin must use HTTPS')
        if set(self.providers) - {'kraken', 'coinbase', 'hyperliquid'}:
            raise ValueError('Unknown provider')

        if self.ntfy_topic and not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', self.ntfy_topic):
            raise ValueError('Invalid private ntfy topic')
) and not (self.access_team and self.access_aud and self.owner_email)):
                raise ValueError('Set strong SESSION_SECRET and OWNER_PASSWORD_HASH before hosting')
            if not self.origin.startswith('https://'):
                raise ValueError('Hosted origin must use HTTPS')
        if set(self.providers) - {'kraken', 'coinbase', 'hyperliquid'}:
            raise ValueError('Unknown provider')

        if self.ntfy_topic and not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', self.ntfy_topic):
            raise ValueError('Invalid private ntfy topic')

        if self.access_aud and (not re.fullmatch(r'https://[a-z0-9-]+\.cloudflareaccess\.com',self.access_team) or '@' not in self.owner_email):
            raise ValueError('Invalid Cloudflare Access configuration')
