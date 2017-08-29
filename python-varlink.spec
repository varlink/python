Name:           python-varlink
Version:        1
Release:        1%{?dist}
Summary:        Python implementation of Varlink
License:        ASL2.0
URL:            https://github.com/varlink/%{name}
Source0:        https://github.com/varlink/%{name}/archive/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel

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
* Tue Aug 29 2017 <info@varlink.org> 1-1
- python-varlink 1
