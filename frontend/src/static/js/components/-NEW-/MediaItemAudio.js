import React from 'react';
import PropTypes from 'prop-types';
import { format } from 'timeago.js'

import { MediaItem } from './MediaItem';

import { PositiveIntegerOrZero } from '../../functions/propTypeFilters';;

import { MediaItemDuration, MediaItemPlaylistIndex, itemClassname } from './includes/items';

import { useMediaItem } from './hooks/useMediaItem';

import { MediaPlaylistOptions } from './MediaPlaylistOptions'

import PageStore from '../../pages/_PageStore.js';
import MediaDurationInfo from '../../classes/MediaDurationInfo';

export function MediaItemAudio(props){

	const type = props.type;

	const [ titleComponent, descriptionComponent, thumbnailUrl, UnderThumbWrapper, editMediaComponent, metaComponents ] = useMediaItem({...props, type });

	const _MediaDurationInfo = new MediaDurationInfo();

	_MediaDurationInfo.update( props.duration );

	const duration = _MediaDurationInfo.ariaLabel();
	const durationStr = _MediaDurationInfo.toString();
	const durationISO8601 = _MediaDurationInfo.ISO8601();

	function thumbnailComponent(){

		const attr = {
			key: 'item-thumb',
			href: props.link,
			title: props.title,
			tabIndex: '-1',
			'aria-hidden': true,
			className: 'item-thumb' + ( ! thumbnailUrl ? ' no-thumb' : '' ),
			style: ! thumbnailUrl ? null : { backgroundImage: 'url(\'' + thumbnailUrl + '\')' },
		};

		return <a {...attr}>
					{ props.inPlaylistView ? null : <MediaItemDuration ariaLabel={ duration } time={ durationISO8601 } text={ durationStr } /> }
				</a>;
	}

	function playlistOrderNumberComponent(){
		return props.hidePlaylistOrderNumber ? null : <MediaItemPlaylistIndex index={ props.playlistOrder } inPlayback={ props.inPlaylistView } activeIndex={ props.playlistActiveItem } />;
	}

	function playlistOptionsComponent(){
		let mediaId = props.link.split("=")[1];
		mediaId = mediaId.split('&')[0];
		return props.hidePlaylistOptions ? null : <MediaPlaylistOptions key="options" media_id={ mediaId } playlist_id={ props.playlist_id } />;
	}

	const containerClassname = itemClassname( 'item ' + type + '-item', props.class_name.trim(), props.playlistOrder === props.playlistActiveItem );

	return (<div className={ containerClassname }>

				{ playlistOrderNumberComponent() }

				<div className="item-content">

					{ editMediaComponent() }

					{ thumbnailComponent() }

					<UnderThumbWrapper title={ props.title } link={ props.link }>
						{ titleComponent() }
						{ metaComponents() }
						{ descriptionComponent() }
					</UnderThumbWrapper>

				{ playlistOptionsComponent() }

				</div>

			</div>);
}

MediaItemAudio.propTypes = {
	...MediaItem.propTypes,
	type: PropTypes.string.isRequired,
	duration: PositiveIntegerOrZero,
	hidePlaylistOptions: PropTypes.bool,
	hasMediaViewer: PropTypes.bool,
	hasMediaViewerDescr: PropTypes.bool,
	playlist_id: PropTypes.string,
};

MediaItemAudio.defaultProps = {
	...MediaItem.defaultProps,
	type: 'audio',
	duration: 0,
	hidePlaylistOptions: true,
	hasMediaViewer: false,
	hasMediaViewerDescr: false,
};
