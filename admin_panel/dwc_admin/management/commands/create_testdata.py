"""
Management command to create test data for DWC Server
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from dwc_admin.models import Console, Profile, NASLogin, BannedItem, GameServer, ServerStatistic
import random


class Command(BaseCommand):
    help = 'Generate test data for DWC Server'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before creating new test data',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            Console.objects.all().delete()
            Profile.objects.all().delete()
            NASLogin.objects.all().delete()
            BannedItem.objects.all().delete()
            GameServer.objects.all().delete()
            ServerStatistic.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Data cleared'))

        self.stdout.write('Creating test data...')

        # Create Consoles
        consoles = []
        console_data = [
            ('00:09:bf:11:22:33', '6818938419496', 'melonDS', 'DS'),
            ('00:16:56:83:31:f9', '2360575017065', 'JonnyD', 'DS'),
            ('00:1f:32:ab:cd:ef', '1234567890123', 'TestWii', 'Wii'),
            ('00:19:1d:99:88:77', '9876543210987', 'MyDSi', 'DSi'),
        ]

        for mac, userid, name, platform in console_data:
            console = Console.objects.create(
                mac_address=mac,
                user_id=userid,
                device_name=name,
                platform=platform,
                enabled=True,
                last_seen=timezone.now() - timedelta(minutes=random.randint(0, 120))
            )
            consoles.append(console)
            self.stdout.write(f'  ✓ Created console: {name} ({mac})')

        # Create Profiles with Friend Codes
        profiles = []
        profile_data = [
            (consoles[0], 'ADAJ', '6818938419496'),  # Pokemon Diamond
            (consoles[1], 'ADAJ', '2360575017065'),  # Pokemon Diamond
            (consoles[1], 'IRAJ', '2360575017065'),  # Pokemon Ranger
            (consoles[2], 'RMCJ', '1234567890123'),  # Mario Kart Wii
            (consoles[3], 'CPUE', '9876543210987'),  # Pokemon Black
        ]

        for console, gameid, userid in profile_data:
            profile = Profile.objects.create(
                user_id=userid,
                game_id=gameid,
                console=console,
                enabled=True,
                gs_broadcast_code=f"{gameid}{random.randint(10,99)}xxx{random.randint(1,9)}",
                uniquenick=f"{console.device_name}_{gameid}"
            )
            profiles.append(profile)
            self.stdout.write(f'  ✓ Created profile: {gameid} for {console.device_name} (FC: {profile.friend_code})')

        # Create NAS Logins
        for i, console in enumerate(consoles):
            for j in range(random.randint(3, 8)):
                NASLogin.objects.create(
                    user_id=console.user_id,
                    auth_token=f"token_{console.user_id}_{j}_{random.randint(1000,9999)}",
                    data={
                        'macadr': console.mac_address,
                        'devname': console.device_name,
                        'action': 'login',
                        'lang': '01',
                    },
                    timestamp=timezone.now() - timedelta(hours=random.randint(0, 72)),
                    ip_address=f"192.168.1.{random.randint(100, 200)}"
                )
        self.stdout.write(f'  ✓ Created NAS login records')

        # Create some bans
        bans = [
            ('ip', '192.168.1.666', 'Suspicious activity', None),
            ('mac', '00:de:ad:be:ef:00', 'Hacking attempt', timezone.now() + timedelta(days=7)),
            ('profile', '12345', 'Cheating', timezone.now() - timedelta(days=1)),  # Expired
        ]

        for ban_type, identifier, reason, expires in bans:
            BannedItem.objects.create(
                ban_type=ban_type,
                identifier=identifier,
                reason=reason,
                expires_at=expires,
                banned_by='admin'
            )
        self.stdout.write(f'  ✓ Created {len(bans)} ban records')

        # Create Game Servers
        if len(profiles) >= 2:
            server_data = [
                (profiles[0], 'pokemondpds', 4, 2),
                (profiles[2], 'pokemonrangerds', 4, 1),
                (profiles[3], 'mariokartwii', 12, 8),
            ]

            for profile, game_name, max_p, curr_p in server_data:
                GameServer.objects.create(
                    server_id=f"{game_name}_{profile.profile_id}_{random.randint(1000,9999)}",
                    game_name=game_name,
                    host_profile=profile,
                    ip_address=f"192.168.1.{random.randint(10, 99)}",
                    port=random.randint(27000, 28000),
                    max_players=max_p,
                    current_players=curr_p,
                    game_data={'mapname': 'test_map', 'gamemode': 'standard'},
                    last_heartbeat=timezone.now() - timedelta(seconds=random.randint(0, 90))
                )
            self.stdout.write(f'  ✓ Created {len(server_data)} game servers')

        # Create Statistics
        for i in range(7):  # Last 7 days
            ServerStatistic.objects.create(
                timestamp=timezone.now() - timedelta(days=i),
                active_consoles=random.randint(50, 150),
                active_profiles=random.randint(80, 200),
                active_servers=random.randint(10, 40),
                total_logins_today=random.randint(200, 500)
            )
        self.stdout.write(f'  ✓ Created 7 days of statistics')

        self.stdout.write(self.style.SUCCESS('\n✅ Test data created successfully!'))
        self.stdout.write(self.style.SUCCESS('\n📊 Summary:'))
        self.stdout.write(f'  - Consoles: {Console.objects.count()}')
        self.stdout.write(f'  - Profiles: {Profile.objects.count()}')
        self.stdout.write(f'  - NAS Logins: {NASLogin.objects.count()}')
        self.stdout.write(f'  - Bans: {BannedItem.objects.count()}')
        self.stdout.write(f'  - Game Servers: {GameServer.objects.count()}')
        self.stdout.write(f'  - Statistics: {ServerStatistic.objects.count()}')
        self.stdout.write('\n👉 Go to http://localhost:8001/admin to see the data!')