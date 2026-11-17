// SPDX-License-Identifier: GPL-3.0-or-later
.pragma library
// Logical pixels, independent of the desktop's unrelated icon-size preference.
var family = "SF Pro Text";
var body = 13;
var caption = 11;
var panelIcon = 18;
var actionIcon = 22;
var circleIcon = 26;
function symbol(name) {
    var names = {"mac-brightness-low":"sun-low", "network-wired-symbolic":"ethernet", "mac-stage-manager":"stage-manager", "mac-mirroring":"mirroring", "mac-appearance":"appearance", "mac-screenshot":"screenshot", "mac-airdrop-off":"airdrop-off", "mac-airplay":"airplay", "mac-speaker-low":"speaker-low", "network-wireless":"wifi", "network-wireless-offline":"wifi-off",
        "preferences-system-bluetooth":"bluetooth", "battery":"battery",
        "weather-clear-night":"moon", "notifications":"bell", "configure":"settings",
        "audio-x-generic":"music", "media-skip-backward":"previous", "media-skip-forward":"next",
        "media-playback-start":"play", "media-playback-pause":"pause",
        "audio-volume-high":"speaker", "audio-volume-muted":"speaker-off", "display-brightness":"sun"};
    if (/^battery-/.test(name)) {
        const level = /^battery-(\d+)/.exec(name);
        const state = name.indexOf("charging") >= 0 ? "charging" : level ? String(Math.max(0,Math.min(100,Math.round(Number(level[1])/10)*10))) : "missing";
        return Qt.resolvedUrl("symbols/mttkde-control-battery-" + state + ".svg");
    }
    if (/^network-wireless/.test(name)) name = /off|disabled|unavailable/.test(name) ? "network-wireless-offline" : "network-wireless";
    return names[name] ? Qt.resolvedUrl("symbols/mttkde-control-" + names[name] + ".svg") : name;
}
