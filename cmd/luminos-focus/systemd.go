// systemd user manager: set runtime CPU properties, clear leftovers from a crashed run.
// [CHANGE: claude-code | 2026-11-07]
package main

import (
	"log"
	"path"
	"strconv"

	"github.com/godbus/dbus/v5"
)

const sdDest, sdMgr = "org.freedesktop.systemd1", "org.freedesktop.systemd1.Manager"
const unset = ^uint64(0) // systemd "infinity"/"not set"

type prop struct {
	Name  string
	Value dbus.Variant
}

type systemd struct{ conn *dbus.Conn } // the production Setter

func (s systemd) Set(unit string, w Want) error {
	q, qs := unset, "none"
	if w.QuotaPct > 0 {
		q, qs = uint64(w.QuotaPct)*10000, strconv.Itoa(w.QuotaPct)
	}
	props := []prop{{"CPUWeight", dbus.MakeVariant(w.Weight)}, {"CPUQuotaPerSecUSec", dbus.MakeVariant(q)}}
	err := s.conn.Object(sdDest, "/org/freedesktop/systemd1").
		Call(sdMgr+".SetUnitProperties", 0, unit, true, props).Err
	if err != nil {
		log.Printf("set %s failed: %v", unit, err)
		return err
	}
	log.Printf("set %s weight=%d quota=%s why=%s", unit, w.Weight, qs, w.Why)
	return nil
}

type unitRow struct {
	Name, Desc, Load, Active, Sub, Follow string
	Path                                  dbus.ObjectPath
	JobID                                 uint32
	JobType                               string
	JobPath                               dbus.ObjectPath
}

// resetLeftovers rests every "app-*" unit directly under app.slice (as AppUnit) with a non-default CPU share.
func (s systemd) resetLeftovers() {
	var rows []unitRow
	err := s.conn.Object(sdDest, "/org/freedesktop/systemd1").
		Call(sdMgr+".ListUnitsByPatterns", 0, []string{}, []string{"app-*"}).Store(&rows)
	if err != nil {
		log.Printf("list units: %v", err)
		return
	}
	for _, r := range rows {
		if s.leftover(r) {
			_ = s.Set(r.Name, Want{100, 0, "leftover"})
		}
	}
}

func (s systemd) leftover(r unitRow) bool {
	iface := map[string]string{".scope": "Scope", ".service": "Service"}[path.Ext(r.Name)]
	if iface == "" {
		return false
	}
	var p map[string]dbus.Variant
	err := s.conn.Object(sdDest, r.Path).
		Call("org.freedesktop.DBus.Properties.GetAll", 0, "org.freedesktop.systemd1."+iface).Store(&p)
	if err != nil {
		return false
	}
	cg, _ := p["ControlGroup"].Value().(string)
	w, _ := p["CPUWeight"].Value().(uint64)
	q, _ := p["CPUQuotaPerSecUSec"].Value().(uint64)
	return path.Base(path.Dir(cg)) == "app.slice" && (w != 100 && w != unset || q != unset)
}
