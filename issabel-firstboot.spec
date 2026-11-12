%define modname firstboot

%if 0%{?rhel} == 7
 %define dist .el7
%endif

Summary: Issabel First Boot Setup
Name:    issabel-firstboot
Version: 6.0.0
Release: 10
License: GPL
Group:   Applications/System
Source0: issabel-%{modname}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{modname}-%{version}-root
BuildArch: noarch
#%if 0%{?el7}
#Requires: mysql, mysql-server, dialog
#%else
Requires: mariadb, mariadb-server, dialog
# issabel-admin-passwords now replays deferred sqlite3 scripts with the sqlite3
# client, so it must be present even if framework is not installed yet.
Requires: sqlite
#%endif
# issabel-admin-passwords opens /var/www/db/acl.db with PDO and connects to
# MariaDB with PDO, but this package declared no PHP dependency at all: it used
# whatever /usr/bin/php happened to be. On EL10 the unversioned php metapackage
# only pulls php-common, not php-cli, so the CLI is required explicitly.
Requires: php-cli
Requires: php-pdo
Requires: php-mysqlnd
Requires: sed, grep
Requires: coreutils
Requires: cracklib
Requires: issabel-config_helpers
# install_amp requires Asterisk to be running, and the service is part of the
# generic asterisk package. Keep the dependency version-agnostic.
Requires: asterisk

Requires(post): chkconfig, /usr/bin/cp
Obsoletes: elastix-firstboot
Provides: elastix-firstboot

# commands: /usr/bin/chvt
Requires: kbd

%description
This module contains (or should contain) utilities and configurations that
cannot be prepared at install time from the ISO image, and are therefore
delayed until the first boot of the newly installed system. The main aim of
this script is to wait until all RPMS are able to either prepare their 
databases on their own, or delegate this task to this package.

%prep
%setup -n %{name}-%{version}

%install
rm -rf $RPM_BUILD_ROOT

mkdir -p $RPM_BUILD_ROOT/etc/init.d/
mkdir -p $RPM_BUILD_ROOT/var/spool/issabel-mysqldbscripts/
mkdir -p $RPM_BUILD_ROOT/usr/share/issabel-firstboot/
mkdir -p $RPM_BUILD_ROOT/usr/bin/
mkdir -p $RPM_BUILD_ROOT/usr/sbin/
mkdir -p $RPM_BUILD_ROOT/usr/local/sbin/
cp issabel-firstboot $RPM_BUILD_ROOT/etc/init.d/
cp change-passwords issabel-admin-passwords $RPM_BUILD_ROOT/usr/bin/
cp issabel-patreon $RPM_BUILD_ROOT/usr/bin/
cp generate_self_signed.sh $RPM_BUILD_ROOT/usr/local/sbin
mv compat-dbscripts/ $RPM_BUILD_ROOT/usr/share/issabel-firstboot/

%post

if [ -d /etc/systemd ] ; then
    cat > /usr/lib/systemd/system/issabel-firstboot.service <<'ISSABELFIRSTBOOT'
[Unit]
Description=issabel-firstboot.service
Wants=mariadb.service asterisk.service
After=mariadb.service
After=asterisk.service

[Service]
Type=oneshot
ExecStart=/usr/bin/bash -c "dmesg -D && chvt 2 && /usr/bin/issabel-admin-passwords --init && chvt 1 && dmesg -E"
#ExecStartPre=-/usr/bin/bash -c "chvt 2 && /usr/src/geoip_install.sh && chvt 1"
ExecReload=/usr/bin/kill -HUP $MAINPID
RemainAfterExit=no
WorkingDirectory=/
Environment=TERM=linux
StandardInput=tty
StandardOutput=tty
TTYPath=/dev/tty2
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=default.target
ISSABELFIRSTBOOT
    systemctl enable issabel-firstboot.service
    # The asterisk RPM uses systemctl preset, and Rocky's preset policy leaves
    # the unit disabled. Firstboot needs it running for install_amp, and the
    # PBX needs it on every boot.
    systemctl enable asterisk.service >/dev/null 2>&1 || :

    cat > /usr/lib/systemd/system/amportal-reload.service <<'AMPORTALRELOAD'
[Unit]
Description=amportal-reload.service
After=asterisk.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/amportal a r
RemainAfterExit=no
WorkingDirectory=/

[Install]
WantedBy=default.target

AMPORTALRELOAD
    systemctl enable amportal-reload.service

    # Show the "wait" notice from early boot and keep the console login closed
    # until the initial configuration has finished. Previously getty@tty1 was
    # available minutes before the firstboot dialogs appeared on tty2, so an
    # administrator could log in while MariaDB still had no root password and
    # install_amp was writing the Asterisk configuration.
    cat > /usr/lib/systemd/system/issabel-firstconfig.service <<'ISSABELFIRSTCONFIG'
[Unit]
Description=Issabel initial configuration notice
# issabelPBX leaves /installamp behind when install_amp could not run during
# its %post (Asterisk was not running), so the marker means the initial
# configuration is still pending.
ConditionPathExists=/installamp
Before=getty@tty1.service
Before=issabel-firstboot.service
After=local-fs.target

[Service]
Type=oneshot
# The box has to stay on screen while MariaDB and Asterisk finish starting, so
# kernel messages are muted here and restored by the `dmesg -E` at the end of
# issabel-firstboot's ExecStart.
ExecStart=/usr/bin/bash -c "dmesg -D; dialog --backtitle 'Issabel' --title ' Issabel ' --infobox 'Wait for initial configuration...\n\nIssabel is preparing the database and the PBX.\nThis can take several minutes. Do not power off the machine.\n\nKernel messages are paused while this runs.' 11 64"
Environment=TERM=linux
StandardInput=tty
StandardOutput=tty
TTYPath=/dev/tty1
TTYReset=no
TTYVHangup=no

[Install]
WantedBy=default.target
ISSABELFIRSTCONFIG
    systemctl enable issabel-firstconfig.service

    # Ordering only: if issabel-firstboot fails, its job ends and the getty
    # still starts, so a broken firstboot cannot leave the console without a
    # login.
    mkdir -p /etc/systemd/system/getty@tty1.service.d
    cat > /etc/systemd/system/getty@tty1.service.d/issabel-firstboot.conf <<'GETTYFIRSTBOOT'
[Unit]
After=issabel-firstboot.service
GETTYFIRSTBOOT

    systemctl daemon-reload >/dev/null 2>&1 || :
else
    chkconfig --del issabel-firstboot
    chkconfig --add issabel-firstboot
    chkconfig --level 2345 issabel-firstboot on
fi

# The following scripts are placed in the spool directory if the corresponding
# database does not exist. This is only temporary and should be removed when the
# corresponding package does this by itself.
if [ ! -d /var/lib/mysql/asteriskcdrdb ] ; then
	cp /usr/share/issabel-firstboot/compat-dbscripts/02-asteriskuser-password.sql /var/spool/issabel-mysqldbscripts/
fi

# If installing, the system might have mysql running (upgrading from a RC).
# The default password is written to the configuration file.
if [ $1 -eq 1 ] ; then
	if [ -e /var/lib/mysql/mysql ] ; then
		if [ ! -e /etc/issabel.conf ] ; then
			echo "Installing in active system - creating empty /etc/issabel.conf"
                        touch /etc/issabel.conf
			#echo "mysqlrootpwd=iSsAbEl.2o17" >> /etc/issabel.conf
		fi
	fi
fi

# If updating, and there is no /etc/issabel.conf , a default file is generated with
# legacy password so new modules continue to work.
if [ $1 -eq 2 ] ; then
	if [ ! -e /etc/issabel.conf ] ; then
		echo "Updating in active system -  creating empty /etc/issabel.conf"
                touch /etc/issabel.conf
		#echo "mysqlrootpwd=iSsAbEl.2o17" >> /etc/issabel.conf
	fi
fi

# If updating, ensure issabel-firstboot now runs at shutdown
if [ $1 -eq 2 ] ; then
    touch /var/lock/subsys/issabel-firstboot
fi

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-, root, root)
%attr(755, root, root) /etc/init.d/*
%dir %{_localstatedir}/spool/issabel-mysqldbscripts/
/usr/share/issabel-firstboot/compat-dbscripts/02-asteriskuser-password.sql
/usr/bin/change-passwords
/usr/bin/issabel-admin-passwords
/usr/bin/issabel-patreon
%attr(755, root, root) /usr/local/sbin/generate_self_signed.sh

%changelog
* Thu Nov 12 2026 Issabel Foundation <info@issabel.org> - 6.0.0-10
- Show a "Wait for initial configuration" notice on tty1 from early boot while
  MariaDB and Asterisk start, and hold getty@tty1 until issabel-firstboot
  finishes. Before this, the console login was available minutes before the
  firstboot dialogs appeared, with MariaDB still having no root password and
  install_amp writing the Asterisk configuration.
- The notice is conditional on /installamp, so it only appears while the
  initial configuration is pending and normal boots are unaffected.
- Drop the dead After=getty@tty2.service ordering: it could make the firstboot
  dialogs die on SIGHUP if getty@tty2 was ever started.

* Wed Nov 11 2026 Issabel Foundation <info@issabel.org> - 6.0.0-9
- Log the result of every deferred database script, with the output of the
  mysql or sqlite3 client, to /var/log/issabel/firstboot-dbsql.log. The output
  was captured and thrown away, so a failing script only left a status and the
  real error (for example "duplicate column name") was lost.
- Show the last lines of that log in the firstboot warning dialog, and point
  the --cli path to the same file. The log self-rotates at 1 MB.

* Sat Nov 07 2026 Issabel Foundation <info@issabel.org> - 6.0.0-8
- Drop the issabel-change-sip step from firstboot: Asterisk 22 no longer
  supports chan_sip. Keep the amportal restart that was part of that step.
- Restart fail2ban at the end of firstboot (and of `--cli init`) so the
  asterisk jail starts after install_amp has generated the logger config and
  /var/log/asterisk/messages exists.

* Sat Nov 07 2026 Issabel Foundation <info@issabel.org> - 6.0.0-7
- Do not pull getty@tty2.service into the firstboot transaction. It takes
  /dev/tty2, and its tty hangup sends SIGHUP to issabel-admin-passwords before
  the password prompts can run.

* Fri Nov 06 2026 Issabel Foundation <info@issabel.org> - 6.0.0-6
- Pull in and enable asterisk.service. The asterisk RPM relies on
  systemctl preset, and Rocky's preset policy leaves it disabled, so firstboot
  ran install_amp without Asterisk and left the asterisk database missing.
- Make action_installIssabelPBX() start and wait for Asterisk, pass the
  existing MariaDB root password on retries, check install_amp's exit status,
  and keep /installamp when it fails so the next boot can retry.
- Stop before the password prompts when IssabelPBX initialization fails, so
  the misleading "IssabelPBX admin password" error is not reported.

* Mon Oct 26 2026 Issabel Foundation <info@issabel.org> - 6.0.0-5
- Apply deferred database scripts with the client recorded by issabel-dbprocess
  (mysql or sqlite3) instead of always using mysql. A sqlite3 script in the
  spool always failed and, worse, aborted the loop, so the scripts behind it
  were never applied.
- Keep going when one deferred script fails, keep the failed script for a
  retry and report the failures instead of dropping them silently.
- Run action_installIssabelPBX() on `--cli init` too, so asteriskuser exists
  before the deferred GRANT statements run.
- Grant endpointconfig and meetme to asteriskuser from the compatibility
  script, which runs once the user exists.

* Fri Oct 09 2026 Issabel Foundation <info@issabel.org> - 6.0.0-4
- Drop the cyrus-imapd/saslpasswd2 setup: Issabel 6 no longer ships a local
  mail server, so the legacy cyrususerpwd is no longer needed.
* Fri Oct 09 2026 Issabel Foundation <info@issabel.org> - 6.0.0-3
- Require the unversioned PHP packages (php-*, 8.3 on EL10) instead of the
  versioned php8.4-*, which conflict with the PHP 8.3 in the netinstall base.
* Thu Oct 08 2026 Issabel Foundation <info@issabel.org> - 6.0.0-2
- Declare the PHP packages issabel-admin-passwords uses: php-cli, php-pdo
  and php-mysqlnd. It opens /var/www/db/acl.db with PDO and connects to
  MariaDB with PDO, but declared no PHP dependency at all, so it used whatever
  /usr/bin/php was.
- issabel-admin-passwords: a failure in one password update no longer aborts the
  rest of the list. The admin password for the framework lives in acl.db and was
  the last entry, so a failing earlier entry (for example the issabelPBX one
  when that package is not installed) left it unset. Failures are now collected
  and reported, and the callers no longer ignore the result.
- issabel-admin-passwords: --init decides "already configured" from the acl_user
  password hash instead of the presence of mysqlrootpwd, so a system that was
  left half configured is repaired instead of being stuck forever.
