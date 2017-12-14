Name:           python-varlink
Version:        2
Release:        1%{?dist}
Summary:        Python implementation of Varlink
License:        ASL2.0
URL:            https://github.com/varlink/%{name}
Source0:        https://github.com/varlink/%{name}/archive/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  pkgconfig(python3) python3-rpm-macros

%description
An python module for Varlink.

%prep
%setup -q

%build
%py3_build

%install
%py3_install

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/*

%changelog
* Thu Dec 14 2017 Harald Hoyer <harald@redhat.com> - 2-1
- python-varlink 2

* Tue Aug 29 2017 <info@varlink.org> 1-1
- python-varlink 1
