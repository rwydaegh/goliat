"""Extended tests for goliat.setups modules."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.skip_on_ci
def test_phantom_setup_initialization():
    """Test PhantomSetup initialization."""
    mock_config = MagicMock()
    mock_config.base_dir = "/tmp"

    # Mock s4l_v1 imports
    mock_s4l_v1 = MagicMock()
    mock_s4l_v1.model = MagicMock()
    mock_s4l_v1.data = MagicMock()
    mock_XCoreModeling = MagicMock()

    def mock_base_init(self, config, verbose_logger, progress_logger):
        """Mock BaseSetup.__init__ that still sets config."""
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger

    with patch("goliat.setups.phantom_setup.BaseSetup.__init__", mock_base_init), patch.dict(
        "sys.modules",
        {
            "s4l_v1": mock_s4l_v1,
            "s4l_v1.data": mock_s4l_v1.data,
            "s4l_v1.model": mock_s4l_v1.model,
            "XCoreModeling": mock_XCoreModeling,
        },
    ):
        from goliat.setups.phantom_setup import PhantomSetup

        setup = PhantomSetup(
            config=mock_config,
            phantom_name="thelonious",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
        )

        assert setup.phantom_name == "thelonious"
        assert setup.config == mock_config


@pytest.mark.skip_on_ci
def test_material_setup_initialization():
    """Test MaterialSetup initialization."""
    mock_config = MagicMock()
    mock_config.base_dir = "/tmp"

    _mock_s4l_v1 = MagicMock()
    mock_XCoreModeling = MagicMock()

    def mock_base_init(self, config, verbose_logger, progress_logger):
        """Mock BaseSetup.__init__ that still sets config."""
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger

    with patch("goliat.setups.material_setup.BaseSetup.__init__", mock_base_init), patch.dict(
        "sys.modules",
        {
            "s4l_v1.materials.database": MagicMock(),
            "XCoreModeling": mock_XCoreModeling,
        },
    ):
        from goliat.setups.material_setup import MaterialSetup

        setup = MaterialSetup(
            config=mock_config,
            simulation=MagicMock(),
            antenna=MagicMock(),
            phantom_name="thelonious",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
        )

        assert setup.config == mock_config
        assert setup.phantom_name == "thelonious"


@pytest.mark.skip_on_ci
def test_placement_setup_initialization():
    """Test PlacementSetup initialization."""
    mock_config = MagicMock()
    mock_config.base_dir = "/tmp"

    mock_XCoreMath = MagicMock()

    def mock_base_init(self, config, verbose_logger, progress_logger):
        """Mock BaseSetup.__init__ that still sets config."""
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger

    with patch("goliat.setups.placement_setup.BaseSetup.__init__", mock_base_init), patch.dict(
        "sys.modules",
        {
            "XCoreMath": mock_XCoreMath,
        },
    ):
        from goliat.setups.placement_setup import PlacementSetup

        setup = PlacementSetup(
            config=mock_config,
            phantom_name="thelonious",
            frequency_mhz=700,
            base_placement_name="by_cheek",
            position_name="center",
            orientation_name="vertical",
            antenna=MagicMock(),
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
        )

        assert setup.config == mock_config
        assert setup.placement_name == "by_cheek_center_vertical"


@pytest.mark.skip_on_ci
def test_source_setup_initialization():
    """Test SourceSetup initialization."""
    mock_config = MagicMock()
    mock_config.base_dir = "/tmp"

    mock_s4l_v1 = MagicMock()
    mock_s4l_v1.units = MagicMock()

    def mock_base_init(self, config, verbose_logger, progress_logger):
        """Mock BaseSetup.__init__ that still sets config."""
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger

    with patch("goliat.setups.source_setup.BaseSetup.__init__", mock_base_init), patch.dict(
        "sys.modules",
        {
            "s4l_v1": mock_s4l_v1,
            "s4l_v1.units": mock_s4l_v1.units,
        },
    ):
        from goliat.setups.source_setup import SourceSetup

        setup = SourceSetup(
            config=mock_config,
            simulation=MagicMock(),
            antenna=MagicMock(),
            frequency_mhz=700,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
        )

        assert setup.config == mock_config
        assert setup.frequency_mhz == 700
