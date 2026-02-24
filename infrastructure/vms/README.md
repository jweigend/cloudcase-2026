# VM-Provisionierung

Platzhalter fuer lokale VM-Umgebungen. Tooling noch offen (Terraform+libvirt, Incus, o.ae.).

Ziel: 5 VMs mit identischer Konfiguration wie die Bare-Metal NUCs bereitstellen,
sodass `inventory/local/hosts.yml` auf die VMs zeigt und alle Ansible-Playbooks
unveraendert laufen.
