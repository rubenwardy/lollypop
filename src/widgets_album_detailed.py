# Copyright (c) 2014-2017 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import GLib, Gtk, Gdk, GObject

from gettext import gettext as _

from lollypop.widgets_rating import RatingWidget
from lollypop.widgets_loved import LovedWidget
from lollypop.widgets_album import AlbumWidget
from lollypop.pop_menu import AlbumMenuPopover, AlbumMenu
from lollypop.widgets_context import ContextWidget
from lollypop.define import WindowSize, Loading
from lollypop.widgets_track import TracksWidget, TrackRow
from lollypop.objects import Track
from lollypop.define import Lp, NextContext, ArtSize, Type


class AlbumDetailedWidget(Gtk.Bin, AlbumWidget):
    """
        Widget with cover and tracks
    """
    __gsignals__ = {
        "populated": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "overlayed": (GObject.SignalFlags.RUN_FIRST, None, (bool,))
    }

    def __init__(self, album_id, genre_ids, artist_ids, art_size):
        """
            Init detailed album widget
            @param album id as int
            @param genre ids as [int]
            @param artist ids as [int]
            @param lazy as LazyLoadingView
            @param art size as ArtSize
        """
        Gtk.Bin.__init__(self)
        AlbumWidget.__init__(self, album_id, genre_ids, artist_ids, art_size)
        self._rounded_class = "rounded-icon-small"
        self._album.set_artists(artist_ids)
        self.__width = None
        self.__context = None
        # Cover + rating + spacing
        self.__height = ArtSize.BIG + 26
        self.__orientation = None
        self.__child_height = TrackRow.get_best_height(self)
        # Header + separator + spacing + margin
        self.__requested_height = self.__child_height + 6
        # Discs to load, will be emptied
        self.__discs = self._album.discs
        self.__locked_widget_right = True
        self.set_property("height-request", self.__height)
        self.connect("size-allocate", self.__on_size_allocate)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Lollypop/AlbumDetailedWidget.ui")
        builder.connect_signals(self)
        self._widget = builder.get_object("widget")
        album_info = builder.get_object("albuminfo")
        title_label = builder.get_object("title")
        title_label.set_property("has-tooltip", True)
        artist_label = builder.get_object("artist")
        artist_label.set_property("has-tooltip", True)
        year_label = builder.get_object("year")
        self.__header = builder.get_object("header")
        self.__overlay = builder.get_object("overlay")
        self.__duration_label = builder.get_object("duration")
        self.__context_button = builder.get_object("context")

        if art_size == ArtSize.NONE:
            self._cover = None
            rating = RatingWidget(self._album)
            rating.set_hexpand(True)
            rating.set_property("halign", Gtk.Align.END)
            rating.set_property("valign", Gtk.Align.CENTER)
            rating.show()
            self.__header.attach(rating, 4, 0, 1, 1)
            loved = LovedWidget(self._album)
            loved.set_property("halign", Gtk.Align.END)
            loved.set_property("valign", Gtk.Align.CENTER)
            loved.show()
            self.__header.attach(loved, 5, 0, 1, 1)

            artist_label.set_text(", ".join(self._album.artists))
            artist_label.show()
            if self._album.year:
                year_label.set_label(self._album.year)
                year_label.show()
        else:
            self.__duration_label.set_hexpand(True)
            builder = Gtk.Builder()
            builder.add_from_resource("/org/gnome/Lollypop/CoverBox.ui")
            builder.connect_signals(self)
            self._play_button = builder.get_object("play-button")
            self._action_button = builder.get_object("action-button")
            self._action_event = builder.get_object("action-event")
            self._cover = builder.get_object("cover")
            self.__coverbox = builder.get_object("coverbox")
            # 6 for 2*3px (application.css)
            self.__coverbox.set_property("width-request", art_size + 6)
            if art_size == ArtSize.BIG:
                self._cover.get_style_context().add_class("cover-frame")
                self._artwork_button = builder.get_object("artwork-button")
                if self._album.year:
                    year_label.set_label(self._album.year)
                    year_label.show()
                grid = Gtk.Grid()
                grid.set_column_spacing(10)
                grid.set_property("halign", Gtk.Align.CENTER)
                grid.show()
                rating = RatingWidget(self._album)
                loved = LovedWidget(self._album)
                rating.show()
                loved.show()
                grid.add(rating)
                grid.add(loved)
                self.__coverbox.add(grid)
                self._widget.attach(self.__coverbox, 0, 0, 1, 1)
                if Lp().window.get_view_width() < WindowSize.MEDIUM:
                    self.__coverbox.hide()
                if len(artist_ids) > 1:
                    artist_label.set_text(", ".join(self._album.artists))
                    artist_label.show()
            elif art_size == ArtSize.HEADER:
                # Here we are working around default CoverBox ui
                # Do we really need to have another ui file?
                # So just hack values on the fly
                self._cover.get_style_context().add_class("small-cover-frame")
                overlay_grid = builder.get_object("overlay-grid")
                overlay_grid.set_margin_bottom(2)
                overlay_grid.set_margin_end(2)
                overlay_grid.set_column_spacing(0)
                play_event = builder.get_object("play-event")
                play_event.set_margin_start(2)
                play_event.set_margin_bottom(2)
                album_info.attach(self.__coverbox, 0, 0, 1, 1)
                artist_label.set_text(", ".join(self._album.artists))
                artist_label.show()

        self.__set_duration()

        self.__box = Gtk.Grid()
        self.__box.set_column_homogeneous(True)
        self.__box.set_property("valign", Gtk.Align.START)
        self.__box.show()
        album_info.add(self.__box)

        self._tracks_left = {}
        self._tracks_right = {}

        self.set_cover()
        self.update_state()

        title_label.set_label(self._album.name)

        for disc in self.__discs:
            self.__add_disc_container(disc.number)
            self.__set_disc_height(disc)

        self.add(self._widget)
        # We start transparent, we switch opaque at size allocation
        # This prevent artifacts
        self.set_opacity(0)

        self._lock_overlay = False
        if self._album.is_web and self._cover is not None:
            self._cover.get_style_context().add_class(
                                                "cover-frame-web")

    def update_playing_indicator(self):
        """
            Update playing indicator
        """
        for disc in self._album.discs:
            self._tracks_left[disc.number].update_playing(
                Lp().player.current_track.id)
            self._tracks_right[disc.number].update_playing(
                Lp().player.current_track.id)

    def update_duration(self, track_id):
        """
            Update duration for current track
            @param track id as int
        """
        for disc in self._album.discs:
            self._tracks_left[disc.number].update_duration(track_id)
            self._tracks_right[disc.number].update_duration(track_id)

    def populate(self):
        """
            Populate tracks
            @thread safe
        """
        if self.__discs:
            disc = self.__discs.pop(0)
            mid_tracks = int(0.5 + len(disc.tracks) / 2)
            self.populate_list_left(disc.tracks[:mid_tracks],
                                    disc,
                                    1)
            self.populate_list_right(disc.tracks[mid_tracks:],
                                     disc,
                                     mid_tracks + 1)

    def is_populated(self):
        """
            Return True if populated
            @return bool
        """
        return len(self.__discs) == 0

    def populate_list_left(self, tracks, disc, pos):
        """
            Populate left list, thread safe
            @param tracks as [Track]
            @param disc as Disc
            @param pos as int
        """
        GLib.idle_add(self.__add_tracks,
                      tracks,
                      self._tracks_left,
                      disc.number,
                      pos)

    def populate_list_right(self, tracks, disc, pos):
        """
            Populate right list, thread safe
            @param tracks as [Track]
            @param disc as Disc
            @param pos as int
        """
        # If we are showing only one column, wait for widget1
        if self.__orientation == Gtk.Orientation.VERTICAL and\
           self.__locked_widget_right:
            GLib.timeout_add(100, self.populate_list_right, tracks, disc, pos)
        else:
            GLib.idle_add(self.__add_tracks,
                          tracks,
                          self._tracks_right,
                          disc.number,
                          pos)

    def get_current_ordinate(self, parent):
        """
            If current track in widget, return it ordinate,
            @param parent widget as Gtk.Widget
            @return y as int
        """
        for dic in [self._tracks_left, self._tracks_right]:
            for widget in dic.values():
                for child in widget.get_children():
                    if child.id == Lp().player.current_track.id:
                        return child.translate_coordinates(parent, 0, 0)[1]
        return None

    def set_filter_func(self, func):
        """
            Set filter function
        """
        for widget in self._tracks_left.values():
            widget.set_filter_func(func)
        for widget in self._tracks_right.values():
            widget.set_filter_func(func)

    @property
    def boxes(self):
        """
            @return [Gtk.ListBox]
        """
        boxes = []
        for widget in self._tracks_left.values():
            boxes.append(widget)
        for widget in self._tracks_right.values():
            boxes.append(widget)
        return boxes

    @property
    def requested_height(self):
        """
            Requested height
        """
        if self.__requested_height < self.__height:
            return self.__height
        else:
            return self.__requested_height

#######################
# PROTECTED           #
#######################
    def _on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        layout = widget.get_layout()
        if layout.is_ellipsized():
            tooltip.set_text(widget.get_label())
        else:
            return False
        return True

    def _on_context_clicked(self, button):
        """
            Show context widget
            @param button as Gtk.Button
        """
        image = button.get_image()
        if self.__context is None:
            image.set_from_icon_name("go-previous-symbolic",
                                     Gtk.IconSize.MENU)
            self.__context = ContextWidget(self._album, button)
            self.__context.set_property("halign", Gtk.Align.START)
            self.__context.set_property("valign", Gtk.Align.CENTER)
            self.__context.show()
            self.__header.insert_next_to(button, Gtk.PositionType.RIGHT)
            self.__header.attach_next_to(self.__context, button,
                                         Gtk.PositionType.RIGHT, 1, 1)
        else:
            image.set_from_icon_name("go-next-symbolic",
                                     Gtk.IconSize.MENU)
            self.__context.destroy()
            self.__context = None

    def _on_album_updated(self, scanner, album_id, destroy):
        """
            On album modified, disable it
            @param scanner as CollectionScanner
            @param album id as int
            @param destroy as bool
        """
        if self._album.id != album_id:
            return
        removed = False
        for dic in [self._tracks_left, self._tracks_right]:
            for widget in dic.values():
                for child in widget.get_children():
                    track = Track(child.id)
                    if track.album.id == Type.NONE:
                        removed = True
        if removed:
            for dic in [self._tracks_left, self._tracks_right]:
                for widget in dic.values():
                    for child in widget.get_children():
                        child.destroy()
            self.__discs = self._album.discs
            self.__set_duration()
            self.populate()
        AlbumWidget._on_album_updated(self, scanner, album_id, destroy)

#######################
# PRIVATE             #
#######################
    def __set_duration(self):
        """
            Set album duration
        """
        duration = Lp().albums.get_duration(self._album.id,
                                            self._album.genre_ids)
        hours = int(duration / 3600)
        mins = int(duration / 60)
        if hours > 0:
            mins -= hours * 60
            if mins > 0:
                self.__duration_label.set_text(_("%s h  %s m") % (hours, mins))
            else:
                self.__duration_label.set_text(_("%s h") % hours)
        else:
            self.__duration_label.set_text(_("%s m") % mins)

    def __set_disc_height(self, disc):
        """
            Set disc widget height
            @param disc as Disc
        """
        count_tracks = len(disc.tracks)
        mid_tracks = int(0.5 + count_tracks / 2)
        left_height = self.__child_height * mid_tracks
        right_height = self.__child_height * (count_tracks - mid_tracks)
        if left_height > right_height:
            self.__requested_height += left_height
        else:
            self.__requested_height += right_height
        self._tracks_left[disc.number].set_property("height-request",
                                                    left_height)
        self._tracks_right[disc.number].set_property("height-request",
                                                     right_height)

    def __add_disc_container(self, disc_number):
        """
            Add disc container to box
            @param disc_number as int
        """
        self._tracks_left[disc_number] = TracksWidget()
        self._tracks_right[disc_number] = TracksWidget()
        self._tracks_left[disc_number].connect("activated",
                                               self.__on_activated)
        self._tracks_right[disc_number].connect("activated",
                                                self.__on_activated)
        self._tracks_left[disc_number].show()
        self._tracks_right[disc_number].show()

    def __pop_menu(self, widget):
        """
            Popup menu for album
            @param widget as Gtk.Button
            @param album id as int
        """
        ancestor = self.get_ancestor(Gtk.Popover)
        # Get album real genre ids (not contextual)
        genre_ids = Lp().albums.get_genre_ids(self._album.id)
        if genre_ids and genre_ids[0] == Type.CHARTS:
            popover = AlbumMenuPopover(self._album, None)
            popover.set_relative_to(widget)
            popover.set_position(Gtk.PositionType.BOTTOM)
        elif self._album.is_web:
            popover = AlbumMenuPopover(self._album,
                                       AlbumMenu(self._album,
                                                 ancestor is not None))
            popover.set_relative_to(widget)
        else:
            popover = Gtk.Popover.new_from_model(
                                            widget,
                                            AlbumMenu(self._album,
                                                      ancestor is not None))
        if ancestor is not None:
            Lp().window.view.show_popover(popover)
        else:
            popover.connect("closed", self.__on_pop_menu_closed)
            self.get_style_context().add_class("album-menu-selected")
            popover.show()

    def __add_tracks(self, tracks, widget, disc_number, i):
        """
            Add tracks for to tracks widget
            @param tracks as [int]
            @param widget as TracksWidget
            @param disc number as int
            @param i as int
        """
        if self._loading == Loading.STOP:
            self._loading = Loading.NONE
            return
        if not tracks:
            if widget == self._tracks_right:
                self._loading |= Loading.RIGHT
            elif widget == self._tracks_left:
                self._loading |= Loading.LEFT
            if self._loading == Loading.ALL:
                self.emit("populated")
            self.__locked_widget_right = False
            return

        track = tracks.pop(0)
        if not Lp().settings.get_value("show-tag-tracknumber"):
            track_number = i
        else:
            track_number = track.number

        row = TrackRow(track.id, track_number)
        row.show()
        widget[disc_number].add(row)
        GLib.idle_add(self.__add_tracks, tracks, widget, disc_number, i + 1)

    def __show_spinner(self, widget, track_id):
        """
            Show spinner for widget
            @param widget as TracksWidget
            @param track id as int
        """
        track = Track(track_id)
        if track.is_web:
            widget.show_spinner(track_id)

    def __on_size_allocate(self, widget, allocation):
        """
            Change box max/min children
            @param widget as Gtk.Widget
            @param allocation as Gtk.Allocation
        """
        if self.__width == allocation.width:
            return
        self.__width = allocation.width
        redraw = False
        # We want vertical orientation
        # when not enought place for cover or tracks
        if allocation.width < WindowSize.MEDIUM or (
                allocation.width < WindowSize.MONSTER and
                self._art_size == ArtSize.BIG):
            orientation = Gtk.Orientation.VERTICAL
        else:
            orientation = Gtk.Orientation.HORIZONTAL
        if orientation != self.__orientation:
            self.__orientation = orientation
            redraw = True

        if redraw:
            for child in self.__box.get_children():
                self.__box.remove(child)
            # Grid index
            idx = 0
            # Disc label width / right box position
            if orientation == Gtk.Orientation.VERTICAL:
                width = 1
                pos = 0
            else:
                width = 2
                pos = 1
            for disc in self._album.discs:
                show_label = len(self._album.discs) > 1
                if show_label:
                    label = Gtk.Label()
                    disc_text = _("Disc %s") % disc.number
                    disc_names = self._album.disc_names(disc.number)
                    if disc_names:
                        disc_text += ": " + ", ".join(disc_names)
                    label.set_text(disc_text)
                    label.set_property("halign", Gtk.Align.START)
                    label.get_style_context().add_class("dim-label")
                    label.show()
                    eventbox = Gtk.EventBox()
                    eventbox.add(label)
                    eventbox.connect("realize",
                                     self.__on_disc_label_realize)
                    eventbox.connect("button-press-event",
                                     self.__on_disc_press_event, disc.number)
                    eventbox.show()
                    self.__box.attach(eventbox, 0, idx, width, 1)
                    idx += 1
                GLib.idle_add(self.__box.attach,
                              self._tracks_left[disc.number],
                              0, idx, 1, 1)
                if orientation == Gtk.Orientation.VERTICAL:
                    idx += 1
                GLib.idle_add(self.__box.attach,
                              self._tracks_right[disc.number],
                              pos, idx, 1, 1)
                idx += 1
                GLib.idle_add(self.set_opacity, 1)
        if self._art_size == ArtSize.BIG:
            if allocation.width < WindowSize.MEDIUM:
                self.__coverbox.hide()
            else:
                self.__coverbox.show()

    def __on_disc_label_realize(self, eventbox):
        """
            Set mouse cursor
            @param eventbox as Gtk.EventBox
        """
        eventbox.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2))

    def __on_disc_press_event(self, eventbox, event, idx):
        """
            Add/Remove disc to/from queue
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
            @param idx as int
        """
        disc = None
        for d in self._album.discs:
            if d.number == idx:
                disc = d
                break
        if disc is None:
            return
        for track in disc.tracks:
            if Lp().player.track_in_queue(track):
                Lp().player.del_from_queue(track.id, False)
            else:
                Lp().player.append_to_queue(track.id, False)
        Lp().player.emit("queue-changed")

    def __on_pop_menu_closed(self, widget):
        """
            Remove selected style
            @param widget as Gtk.Popover
        """
        self.get_style_context().remove_class("album-menu-selected")

    def __on_activated(self, widget, track_id):
        """
            On track activation, play track
            @param widget as TracksWidget
            @param track id as int
        """
        # Add to queue by default
        if Lp().player.locked:
            if track_id in Lp().player.queue:
                Lp().player.del_from_queue(track_id)
            else:
                Lp().player.append_to_queue(track_id)
        else:
            if not Lp().player.has_album(self._album):
                Lp().player.clear_albums()
                Lp().player.play_album(self._album)

            self.__show_spinner(widget, track_id)
            track = Track(track_id)
            Lp().player.load(track)
