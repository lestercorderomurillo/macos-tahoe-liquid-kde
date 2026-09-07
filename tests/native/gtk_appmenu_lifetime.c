// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise a real GTK module across settings changes on a private display/bus.
#include <gtk/gtk.h>
#include <stdio.h>
#include <string.h>
#include <sys/prctl.h>

static int module_mapped(void)
{
    FILE *maps = fopen("/proc/self/maps", "r");
    char line[4096];
    int found = 0;
    while (maps && fgets(line, sizeof line, maps)) {
        if (strstr(line, "libappmenu-gtk-module.so")) {
            found = 1;
        }
    }
    if (maps) {
        fclose(maps);
    }
    return found;
}

static void dispatch_callbacks(void)
{
    gint64 until = g_get_monotonic_time() + 20000;
    while (g_get_monotonic_time() < until) {
        while (g_main_context_iteration(NULL, FALSE)) {}
        g_usleep(1000);
    }
}

int main(int argc, char **argv)
{
    // The unprotected control may crash. Never send a core to the host handler.
    if (prctl(PR_SET_DUMPABLE, 0) != 0) {
        return 2;
    }
    if (!gtk_init_check(&argc, &argv)) {
        return 2;
    }
    GtkSettings *settings = gtk_settings_get_default();
    g_object_set(settings, "gtk-modules", "appmenu-gtk-module", NULL);
    g_print("loaded: %d\n", module_mapped());
    g_object_set(settings, "gtk-modules", "", NULL);
    g_print("after settings removal: %d\n", module_mapped());
    dispatch_callbacks();

    for (int i = 0; i < 25; ++i) {
        guint owner = g_bus_own_name(G_BUS_TYPE_SESSION, "com.canonical.AppMenu.Registrar",
                                    G_BUS_NAME_OWNER_FLAGS_NONE, NULL, NULL, NULL, NULL, NULL);
        g_object_set(settings, "gtk-modules", "appmenu-gtk-module", NULL);
        dispatch_callbacks();
        g_object_set(settings, "gtk-modules", "", NULL);
        g_bus_unown_name(owner);
        dispatch_callbacks();
        if (!module_mapped()) {
            return 3;
        }
    }

    // Also exercise the GtkMenuBar vfuncs replaced by the module.
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    GtkWidget *menu = gtk_menu_bar_new();
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), gtk_menu_item_new_with_label("File"));
    gtk_container_add(GTK_CONTAINER(window), menu);
    gtk_widget_show_all(window);
    dispatch_callbacks();
    gtk_widget_destroy(window);
    g_print("PASS: 25 settings/registrar cycles and GTK menu vfuncs\n");
    return 0;
}
