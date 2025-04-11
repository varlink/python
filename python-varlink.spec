Name:           python-varlink
Version: 	30.3.1
Release:        1%{?dist}
Summary:        Python implementation of Varlink
License:        ASL 2.0
URL:            https://github.com/varlink/%{name}
Source0:        https://github.com/varlink/%{name}/archive/%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-rpm-macros
BuildRequires:  python3-setuptools
BuildRequires:  python3-setuptools_scm


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
export SETUPTOOLS_SCM_PRETEND_VERSION=%{version}
%py3_build

%check
export SETUPTOOLS_SCM_PRETEND_VERSION=%{version}
CFLAGS="%{optflags}" %{__python3} %{py_setup} %{?py_setup_args} check

%install
export SETUPTOOLS_SCM_PRETEND_VERSION=%{version}
%py3_install

%files -n python3-varlink
%license LICENSE.txt
%doc README.md
%{python3_sitelib}/*

%changelog
