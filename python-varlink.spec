%define build_date %(date +"%%a %%b %%d %%Y")
%define build_timestamp %(date +"%%Y%%m%%d.%%H%M%%S")

Name:           python-varlink
Version:        1
Release:        %{build_timestamp}%{?dist}
Summary:        Python implementation of Varlink
License:        ASL2.0
URL:            https://github.com/varlink/python-varlink
Source0:        https://github.com/varlink/python-varlink/archive/v%{version}.tar.gz

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
* %{build_date} <info@varlink.org> %{version}-%{build_timestamp}
- %{name} %{version}
