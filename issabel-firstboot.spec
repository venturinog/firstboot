%define modname firstboot

%if 0%{?rhel} == 7
 %define dist .el7
%endif

Summary: Issabel First Boot Setup
Name:    issabel-firstboot
Version: 6.0.0
Release: 5
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
After=getty@tty2.service
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
