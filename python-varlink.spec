Name:           python-varlink
Version: 	30.1.2
Release:        1%{?dist}
Summary:        Python implementation of Varlink
License:        ASL 2.0
URL:            https://github.com/varlink/%{name}
Source0:        https://github.com/varlink/%{name}/archive/%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-rpm-macros

%global _description \
An python module for Varlink with client and server support.

%description %_description

%package -n python3-varlink
Summary:       %summary
%{?python_provide:%python_provide python3-varlink}

%description -n python3-varlink %_description

%prep
%autosetup -n python-%{version}

%build
%py3_build

%check
CFLAGS="%{optflags}" %{__python3} %{py_setup} %{?py_setup_args} check

%install
%py3_install

%files -n python3-varlink
%license LICENSE.txt
%doc README.md
%{python3_sitelib}/*

%changelog
